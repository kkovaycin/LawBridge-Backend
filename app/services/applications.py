from app.models.schemas import ApplicationDraftRequest, ApplicationDraftResponse


def create_application_draft(request: ApplicationDraftRequest) -> ApplicationDraftResponse:
    legal_topic = request.legal_topic or "hukuki risk değerlendirmesi"
    applicant = request.applicant_name or "[Başvurucu adı]"

    draft = f"""{request.recipient}

KONU: {legal_topic} hakkında başvuru ve inceleme talebidir.

BAŞVURUCU:
{applicant}

AÇIKLAMALAR:
1. Başvuruya konu olay ve içerik aşağıda özetlenmiştir:
{request.text}

2. İçeriğin hukuki niteliği ilk değerlendirmede "{legal_topic}" başlığı altında incelenmiştir.

3. İlgili URL, ekran görüntüsü, tarih-saat bilgisi, mesaj kayıtları ve varsa ödeme veya kimlik bilgileri delil olarak ayrıca sunulacaktır.

TALEP:
Yukarıda açıklanan nedenlerle başvuruya konu içeriğin incelenmesini, gerekli tespitlerin yapılmasını ve uygun hukuki işlemlerin başlatılmasını arz ederim.

Tarih:
İmza:
"""

    return ApplicationDraftResponse(
        title=f"{legal_topic} başvuru taslağı",
        draft=draft,
        warnings=[
            "Bu çıktı otomatik taslaktır; hukuki görüş yerine geçmez.",
            "Başvuru öncesinde delil bütünlüğü ve yetkili merci kontrol edilmelidir.",
        ],
    )
