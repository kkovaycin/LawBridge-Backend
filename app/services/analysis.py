from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from app.models.schemas import (
    ActionLink,
    AnalysisCardResult,
    AnalysisResponse,
    AnalysisType,
    AnalyzeRequest,
    AnalyzeSourceType,
    Classifications,
    ClassificationResponse,
    PrecedentMatch,
    RiskLevel,
    YouTubeAnalysisStats,
    YouTubeCommentAnalysis,
)
from app.services.registry import ModelRegistry
from app.services.youtube import YouTubeComment, extract_youtube_video_id


RISK_LABELS = {
    RiskLevel.low: "Düşük risk",
    RiskLevel.medium: "Orta risk",
    RiskLevel.high: "Yüksek risk",
}

SOURCE_LABELS = {
    "text-comment": "Metin / Yorum",
    "social-media-link": "Sosyal Medya Bağlantısı",
    "youtube-comment": "YouTube Yorumu",
    "document-text": "Belge Metni",
}

ANALYSIS_TITLES = {
    AnalysisType.insult_threat: "Hakaret / Tehdit",
    AnalysisType.fraud: "Dolandırıcılık Şüphesi",
    AnalysisType.personal_rights: "Kişilik Hakkı İhlali",
    AnalysisType.general_risk: "Genel Hukuki Risk",
}


@dataclass(frozen=True)
class TextEvaluation:
    text: str
    sentiment: ClassificationResponse
    intent: ClassificationResponse
    legal: ClassificationResponse
    analysis_type: AnalysisType
    risk_level: RiskLevel
    legal_topic: str


class AnalysisService:
    def __init__(self, registry: ModelRegistry) -> None:
        self.registry = registry

    def analyze(self, request: AnalyzeRequest) -> AnalysisResponse:
        if request.source_type == AnalyzeSourceType.youtube_comment:
            video_id = extract_youtube_video_id(request.text)
            if video_id:
                return self._analyze_youtube_video(request, video_id)

        evaluation = self._evaluate_text(request.text, request.analysis_type)
        precedent_matches = self.registry.precedents.search(request.text, top_k=3)
        summary = self._summary(
            text=request.text,
            legal=evaluation.legal,
            intent=evaluation.intent,
            sentiment=evaluation.sentiment,
            risk_level=evaluation.risk_level,
        )

        return self._build_response(
            request=request,
            input_text=request.text,
            evaluation=evaluation,
            precedent_matches=precedent_matches,
            summary=summary,
            recommended_actions=self._recommended_actions(
                evaluation.analysis_type,
                evaluation.risk_level,
            ),
            precedent_suggestion=self._precedent_suggestion(
                precedent_matches,
                evaluation.analysis_type,
            ),
        )

    def _evaluate_text(
        self,
        text: str,
        requested_analysis_type: AnalysisType | None,
    ) -> TextEvaluation:
        sentiment = self.registry.sentiment.predict(text, top_k=5)
        intent = self.registry.intent.predict(text, top_k=5)
        legal = self.registry.legal.predict(text, top_k=5)
        analysis_type = requested_analysis_type or self._infer_analysis_type(
            legal=legal,
            intent=intent,
            text=text,
        )
        risk_level = self._infer_risk_level(
            legal=legal,
            intent=intent,
            sentiment=sentiment,
            text=text,
            analysis_type=analysis_type,
        )
        legal_topic = self._legal_topic(legal, analysis_type)

        return TextEvaluation(
            text=text,
            sentiment=sentiment,
            intent=intent,
            legal=legal,
            analysis_type=analysis_type,
            risk_level=risk_level,
            legal_topic=legal_topic,
        )

    def _analyze_youtube_video(
        self,
        request: AnalyzeRequest,
        video_id: str,
    ) -> AnalysisResponse:
        comments = self.registry.youtube.fetch_video_comments(video_id)
        evaluated_comments = [
            (comment, self._evaluate_text(comment.text, request.analysis_type))
            for comment in comments
        ]

        sorted_comments = sorted(
            evaluated_comments,
            key=lambda item: (
                self._risk_rank(item[1].risk_level),
                item[1].legal.primary_score,
                item[1].intent.primary_score,
            ),
            reverse=True,
        )
        flagged_comments = [
            item
            for item in sorted_comments
            if item[1].risk_level in {RiskLevel.high, RiskLevel.medium}
        ]
        representative_comment, representative_evaluation = sorted_comments[0]
        risk_level = self._overall_youtube_risk(evaluated_comments)
        representative_evaluation = TextEvaluation(
            text=representative_evaluation.text,
            sentiment=representative_evaluation.sentiment,
            intent=representative_evaluation.intent,
            legal=representative_evaluation.legal,
            analysis_type=representative_evaluation.analysis_type,
            risk_level=risk_level,
            legal_topic=representative_evaluation.legal_topic,
        )

        search_text = self._youtube_search_text(flagged_comments or sorted_comments)
        precedent_matches = self.registry.precedents.search(search_text, top_k=3)
        stats = self._youtube_stats(video_id, evaluated_comments, flagged_comments)
        top_comment_results = [
            self._youtube_comment_result(comment, evaluation)
            for comment, evaluation in (flagged_comments or sorted_comments)[:5]
        ]
        summary = self._youtube_summary(
            video_id=video_id,
            stats=stats,
            representative_comment=representative_comment,
            representative_evaluation=representative_evaluation,
        )

        return self._build_response(
            request=request,
            input_text=self._youtube_input_text(video_id, comments),
            evaluation=representative_evaluation,
            precedent_matches=precedent_matches,
            summary=summary,
            recommended_actions=self._youtube_recommended_actions(
                representative_evaluation.analysis_type,
                risk_level,
                stats.flagged_count,
            ),
            precedent_suggestion=self._precedent_suggestion(
                precedent_matches,
                representative_evaluation.analysis_type,
            ),
            title="YouTube Yorum Analizi",
            youtube_stats=stats,
            youtube_comments=top_comment_results,
        )

    def _build_response(
        self,
        request: AnalyzeRequest,
        input_text: str,
        evaluation: TextEvaluation,
        precedent_matches: list[PrecedentMatch],
        summary: str,
        recommended_actions: list[str],
        precedent_suggestion: str,
        title: str | None = None,
        youtube_stats: YouTubeAnalysisStats | None = None,
        youtube_comments: list[YouTubeCommentAnalysis] | None = None,
    ) -> AnalysisResponse:
        title = title or ANALYSIS_TITLES[evaluation.analysis_type]

        result = AnalysisCardResult(
            risk_level=RISK_LABELS[evaluation.risk_level],
            legal_topic=evaluation.legal_topic,
            summary=summary,
            recommended_actions=recommended_actions,
            precedent_suggestion=precedent_suggestion,
            actions=[
                ActionLink(
                    href="/dashboard/precedents",
                    label="Emsal kararlara git",
                    variant="secondary",
                ),
                ActionLink(
                    href="/dashboard/applications",
                    label="Taslak hazırlığına geç",
                    variant="primary",
                ),
            ],
            youtube_stats=youtube_stats,
            youtube_comments=youtube_comments or [],
        )

        return AnalysisResponse(
            id=f"analysis-{uuid4().hex[:12]}",
            title=title,
            input_text=input_text,
            source_type=SOURCE_LABELS[request.source_type.value],
            analyze_source_type=request.source_type,
            analysis_type=evaluation.analysis_type,
            risk_level=evaluation.risk_level,
            risk_label=RISK_LABELS[evaluation.risk_level],
            legal_topic=evaluation.legal_topic,
            summary=summary,
            recommended_actions=recommended_actions,
            precedent_suggestion=precedent_suggestion,
            precedent_matches=precedent_matches,
            classifications=Classifications(
                sentiment=evaluation.sentiment,
                intent=evaluation.intent,
                legal=evaluation.legal,
            ),
            result=result,
            created_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _overall_youtube_risk(
        evaluated_comments: list[tuple[YouTubeComment, TextEvaluation]],
    ) -> RiskLevel:
        risks = [evaluation.risk_level for _, evaluation in evaluated_comments]
        if RiskLevel.high in risks:
            return RiskLevel.high
        if RiskLevel.medium in risks:
            return RiskLevel.medium
        return RiskLevel.low

    @staticmethod
    def _risk_rank(risk_level: RiskLevel) -> int:
        return {
            RiskLevel.low: 0,
            RiskLevel.medium: 1,
            RiskLevel.high: 2,
        }[risk_level]

    def _youtube_stats(
        self,
        video_id: str,
        evaluated_comments: list[tuple[YouTubeComment, TextEvaluation]],
        flagged_comments: list[tuple[YouTubeComment, TextEvaluation]],
    ) -> YouTubeAnalysisStats:
        return YouTubeAnalysisStats(
            video_id=video_id,
            comment_count=len(evaluated_comments),
            flagged_count=len(flagged_comments),
            high_risk_count=sum(
                1 for _, evaluation in evaluated_comments if evaluation.risk_level == RiskLevel.high
            ),
            medium_risk_count=sum(
                1 for _, evaluation in evaluated_comments if evaluation.risk_level == RiskLevel.medium
            ),
            low_risk_count=sum(
                1 for _, evaluation in evaluated_comments if evaluation.risk_level == RiskLevel.low
            ),
            analyzed_comment_limit=self.registry.settings.youtube_max_comments,
        )

    @staticmethod
    def _youtube_comment_result(
        comment: YouTubeComment,
        evaluation: TextEvaluation,
    ) -> YouTubeCommentAnalysis:
        return YouTubeCommentAnalysis(
            id=comment.id,
            author=comment.author,
            text=AnalysisService._clip(comment.text, 500),
            published_at=comment.published_at,
            like_count=comment.like_count,
            risk_level=evaluation.risk_level,
            risk_label=RISK_LABELS[evaluation.risk_level],
            legal_topic=evaluation.legal_topic,
            analysis_type=evaluation.analysis_type,
            primary_legal_label=evaluation.legal.primary_label,
            primary_legal_score=evaluation.legal.primary_score,
        )

    @staticmethod
    def _youtube_summary(
        video_id: str,
        stats: YouTubeAnalysisStats,
        representative_comment: YouTubeComment,
        representative_evaluation: TextEvaluation,
    ) -> str:
        flagged_sentence = (
            f"{stats.flagged_count} yorum orta veya yuksek risk isareti tasiyor."
            if stats.flagged_count
            else "Orta veya yuksek risk tasiyan yorum bulunmadi."
        )
        clipped_comment = AnalysisService._clip(representative_comment.text, 220)

        return (
            f"YouTube videosundan {stats.comment_count} yorum cekildi ve mevcut modellerle "
            f"tek tek incelendi. {flagged_sentence} En belirgin yorum "
            f"{RISK_LABELS[representative_evaluation.risk_level].lower()} olarak degerlendirildi. "
            f"Video ID: {video_id}. Incelenen yorum: {clipped_comment}"
        )

    @staticmethod
    def _youtube_recommended_actions(
        analysis_type: AnalysisType,
        risk_level: RiskLevel,
        flagged_count: int,
    ) -> list[str]:
        actions = AnalysisService._recommended_actions(analysis_type, risk_level)
        actions.insert(
            0,
            "Video linkini, yorum metinlerini, yorum tarihlerini ve ekran goruntulerini birlikte arsivleyin.",
        )
        if flagged_count:
            actions.insert(
                1,
                "Riskli gorunen yorumlari tek tek alintilayarak hangi kullanici tarafindan yazildigini not edin.",
            )
        return actions

    @staticmethod
    def _youtube_search_text(
        evaluated_comments: list[tuple[YouTubeComment, TextEvaluation]],
    ) -> str:
        comments = [comment.text for comment, _ in evaluated_comments[:10]]
        return "\n".join(comments)

    @staticmethod
    def _youtube_input_text(video_id: str, comments: list[YouTubeComment]) -> str:
        comment_lines = [
            f"{index}. {comment.author or 'Anonim'}: {AnalysisService._clip(comment.text, 700)}"
            for index, comment in enumerate(comments, start=1)
        ]
        return (
            f"https://www.youtube.com/watch?v={video_id}\n\n"
            f"Cekilen YouTube yorumlari ({len(comments)}):\n"
            + "\n".join(comment_lines)
        )

    @staticmethod
    def _clip(text: str, max_length: int) -> str:
        normalized = " ".join(text.strip().split())
        if len(normalized) <= max_length:
            return normalized
        return f"{normalized[: max_length - 3].rstrip()}..."

    def _infer_analysis_type(
        self,
        legal: ClassificationResponse,
        intent: ClassificationResponse,
        text: str,
    ) -> AnalysisType:
        combined = " ".join(
            [
                legal.primary_label,
                intent.primary_label,
                text,
            ]
        ).casefold()

        if "dolandırıcılık" in combined or "sahte kampanya" in combined:
            return AnalysisType.fraud

        if any(keyword in combined for keyword in ["hakaret", "tehdit", "taciz", "aşağılama"]):
            return AnalysisType.insult_threat

        if any(keyword in combined for keyword in ["veri", "kvkk", "kişilik", "mahremiyet", "fotoğraf", "itibar"]):
            return AnalysisType.personal_rights

        return AnalysisType.general_risk

    def _infer_risk_level(
        self,
        legal: ClassificationResponse,
        intent: ClassificationResponse,
        sentiment: ClassificationResponse,
        text: str,
        analysis_type: AnalysisType,
    ) -> RiskLevel:
        labels = legal.labels + intent.labels + sentiment.labels
        passed_labels = [item for item in labels if item.passed_threshold]
        signal_text = " ".join(
            [item.label for item in passed_labels or labels[:3]] + [text]
        ).casefold()
        top_score = max(item.score for item in labels)

        high_keywords = [
            "tehdit",
            "hakaret",
            "dolandırıcılık",
            "nefret",
            "taciz",
            "veri ihlali",
            "kin",
            "kamu görevlisine",
        ]

        if any(keyword in signal_text for keyword in high_keywords) and analysis_type in {
            AnalysisType.insult_threat,
            AnalysisType.fraud,
            AnalysisType.personal_rights,
        }:
            return RiskLevel.high

        if "uygunsuzluk yok" in legal.primary_label.casefold() and legal.primary_score >= 0.7:
            return RiskLevel.low

        if any(keyword in signal_text for keyword in high_keywords) and top_score >= 0.5:
            return RiskLevel.high

        if top_score >= 0.45:
            return RiskLevel.medium

        return RiskLevel.low

    @staticmethod
    def _legal_topic(legal: ClassificationResponse, analysis_type: AnalysisType) -> str:
        if legal.primary_label and "uygunsuzluk yok" not in legal.primary_label.casefold():
            return legal.primary_label

        return {
            AnalysisType.insult_threat: "Hakaret ve tehdit değerlendirmesi",
            AnalysisType.fraud: "Dolandırıcılık şüphesi",
            AnalysisType.personal_rights: "Kişilik hakkı ve veri ihlali değerlendirmesi",
            AnalysisType.general_risk: "Genel hukuki risk değerlendirmesi",
        }[analysis_type]

    @staticmethod
    def _summary(
        text: str,
        legal: ClassificationResponse,
        intent: ClassificationResponse,
        sentiment: ClassificationResponse,
        risk_level: RiskLevel,
    ) -> str:
        clipped = text.strip().replace("\n", " ")
        if len(clipped) > 220:
            clipped = f"{clipped[:217].rstrip()}..."

        return (
            f"Metin {RISK_LABELS[risk_level].lower()} düzeyinde değerlendirildi. "
            f"Legal model en güçlü başlık olarak '{legal.primary_label}' sonucunu, "
            f"intent modeli '{intent.primary_label}' sonucunu ve sentiment modeli "
            f"'{sentiment.primary_label}' duygu durumunu öne çıkardı. "
            f"İncelenen içerik: {clipped}"
        )

    @staticmethod
    def _recommended_actions(analysis_type: AnalysisType, risk_level: RiskLevel) -> list[str]:
        base_actions = [
            "İçeriğin URL, tarih, saat ve ekran görüntüsü gibi delil bilgilerini birlikte saklayın.",
            "Metindeki kişi, platform ve olay bağlamını kısa bir kronoloji halinde netleştirin.",
        ]

        type_actions = {
            AnalysisType.insult_threat: "Hakaret veya tehdit içeren ifadeleri doğrudan alıntılayarak ayrı bir delil notu hazırlayın.",
            AnalysisType.fraud: "Ödeme kayıtları, mesaj akışı ve karşı taraf kimlik bilgilerini tek dosyada toplayın.",
            AnalysisType.personal_rights: "İhlalin ad, görsel, iletişim bilgisi veya itibar boyutunu ayrı başlıklarla işaretleyin.",
            AnalysisType.general_risk: "Belirsiz kalan hukuki başlıklar için ek bağlam ve belge ekleyerek yeniden analiz yapın.",
        }

        if risk_level == RiskLevel.high:
            base_actions.append("Yüksek risk nedeniyle hızlı emsal taraması ve profesyonel hukuki değerlendirme planlayın.")

        base_actions.append(type_actions[analysis_type])
        return base_actions

    @staticmethod
    def _precedent_suggestion(
        matches: list[PrecedentMatch],
        analysis_type: AnalysisType,
    ) -> str:
        if matches:
            best = matches[0].precedent
            return f"Öncelikle '{best.title}' başlıklı emsal kaydıyla benzerlik kontrolü yapın."

        return {
            AnalysisType.insult_threat: "Kamuya açık yorumlarda hakaret ve tehdit içeren kararlara öncelik verin.",
            AnalysisType.fraud: "Online para talebi ve yanıltıcı bağlantı içeren karar başlıklarına bakın.",
            AnalysisType.personal_rights: "Kişilik hakkını veya kişisel veriyi etkileyen dijital içerik kararlarını öne alın.",
            AnalysisType.general_risk: "Platform ve içerik türüne göre geniş kapsamlı emsal başlıklarıyla başlayın.",
        }[analysis_type]
