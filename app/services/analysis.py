from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.models.schemas import (
    ActionLink,
    AnalysisCardResult,
    AnalysisResponse,
    AnalysisType,
    AnalyzeRequest,
    Classifications,
    ClassificationResponse,
    PrecedentMatch,
    RiskLevel,
)
from app.services.registry import ModelRegistry


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


class AnalysisService:
    def __init__(self, registry: ModelRegistry) -> None:
        self.registry = registry

    def analyze(self, request: AnalyzeRequest) -> AnalysisResponse:
        sentiment = self.registry.sentiment.predict(request.text, top_k=5)
        intent = self.registry.intent.predict(request.text, top_k=5)
        legal = self.registry.legal.predict(request.text, top_k=5)
        analysis_type = request.analysis_type or self._infer_analysis_type(
            legal=legal,
            intent=intent,
            text=request.text,
        )
        risk_level = self._infer_risk_level(
            legal=legal,
            intent=intent,
            sentiment=sentiment,
            text=request.text,
            analysis_type=analysis_type,
        )
        precedent_matches = self.registry.precedents.search(request.text, top_k=3)
        legal_topic = self._legal_topic(legal, analysis_type)
        summary = self._summary(
            text=request.text,
            legal=legal,
            intent=intent,
            sentiment=sentiment,
            risk_level=risk_level,
        )
        recommended_actions = self._recommended_actions(analysis_type, risk_level)
        precedent_suggestion = self._precedent_suggestion(precedent_matches, analysis_type)
        title = ANALYSIS_TITLES[analysis_type]

        result = AnalysisCardResult(
            risk_level=RISK_LABELS[risk_level],
            legal_topic=legal_topic,
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
        )

        return AnalysisResponse(
            id=f"analysis-{uuid4().hex[:12]}",
            title=title,
            input_text=request.text,
            source_type=SOURCE_LABELS[request.source_type.value],
            analyze_source_type=request.source_type,
            analysis_type=analysis_type,
            risk_level=risk_level,
            risk_label=RISK_LABELS[risk_level],
            legal_topic=legal_topic,
            summary=summary,
            recommended_actions=recommended_actions,
            precedent_suggestion=precedent_suggestion,
            precedent_matches=precedent_matches,
            classifications=Classifications(
                sentiment=sentiment,
                intent=intent,
                legal=legal,
            ),
            result=result,
            created_at=datetime.now(timezone.utc),
        )

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
