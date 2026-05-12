from app.models.schemas import PrecedentRecord, RiskLevel


PRECEDENTS: list[PrecedentRecord] = [
    PrecedentRecord(
        id="precedent-001",
        title="Sosyal medya paylaşımında onur, şeref ve saygınlığa saldırı değerlendirmesi",
        court="Yargıtay 12. Ceza Dairesi",
        date="2025-11-14",
        summary=(
            "Herkese açık sosyal medya paylaşımında mağduru küçük düşürücü ifadelerin "
            "aleniyet ve hedef gösterme etkisiyle birlikte değerlendirilmesi gerektiği kabul edildi."
        ),
        tags=["Hakaret", "Sosyal medya"],
        risk_level=RiskLevel.high,
        saved=True,
    ),
    PrecedentRecord(
        id="precedent-002",
        title="Sahte ödeme bağlantısı ile menfaat teminine yönelik mesaj zinciri",
        court="İstanbul Bölge Adliye Mahkemesi 7. Ceza Dairesi",
        date="2025-09-03",
        summary=(
            "Mesajlaşma uygulaması üzerinden gönderilen sahte ödeme bağlantılarının "
            "kullanıcıyı yanıltmaya elverişli hileli davranış niteliği taşıdığı değerlendirildi."
        ),
        tags=["Dolandırıcılık", "Mesajlaşma"],
        risk_level=RiskLevel.high,
        saved=False,
    ),
    PrecedentRecord(
        id="precedent-003",
        title="İzinsiz fotoğraf ve isim kullanımı nedeniyle kişilik hakkı ihlali",
        court="Yargıtay 4. Hukuk Dairesi",
        date="2025-07-28",
        summary=(
            "Kişinin adı ve görselinin rızası dışında dijital içerikte kullanılması halinde "
            "manevi tazminat koşullarının oluşabileceği vurgulandı."
        ),
        tags=["Kişilik hakkı", "İçerik kaldırma"],
        risk_level=RiskLevel.medium,
        saved=True,
    ),
    PrecedentRecord(
        id="precedent-004",
        title="Kurumsal itibarı zedeleyen doğrulanmamış suç isnadı",
        court="Ankara Bölge Adliye Mahkemesi 25. Hukuk Dairesi",
        date="2025-05-19",
        summary=(
            "Somut delile dayanmayan suçlayıcı ifadelerin çevrim içi ortamda yayılmasının "
            "ticari itibar üzerinde hukuka aykırı etki doğurabileceği belirtildi."
        ),
        tags=["İftira", "İtibar"],
        risk_level=RiskLevel.medium,
        saved=False,
    ),
    PrecedentRecord(
        id="precedent-005",
        title="Israrlı gece mesajlarının huzur ve sükunu bozma kapsamında incelenmesi",
        court="Yargıtay 18. Ceza Dairesi",
        date="2025-03-11",
        summary=(
            "Tekrarlayan mesajların içerik, saat aralığı ve mağdurun rahatsızlığını gösteren "
            "beyanlarla birlikte süreklilik unsuru taşıyabileceği kabul edildi."
        ),
        tags=["Taciz", "WhatsApp"],
        risk_level=RiskLevel.medium,
        saved=False,
    ),
    PrecedentRecord(
        id="precedent-006",
        title="Arama motoru sonucunda erişimin engellenmesi talebine ilişkin denge testi",
        court="Anayasa Mahkemesi Bireysel Başvuru",
        date="2024-12-06",
        summary=(
            "Eski tarihli içeriğin kişisel itibara etkisi değerlendirilirken güncellik, "
            "kamu yararı ve kişisel menfaat dengesinin kurulması gerektiği açıklandı."
        ),
        tags=["Kişilik hakkı", "Arama sonuçları"],
        risk_level=RiskLevel.low,
        saved=True,
    ),
    PrecedentRecord(
        id="precedent-007",
        title="Elektronik posta yoluyla yöneltilen tehdit içerikli ifadelerin delil değeri",
        court="İzmir 3. Ağır Ceza Mahkemesi",
        date="2024-10-22",
        summary=(
            "E-posta başlık bilgileri, gönderim zamanı ve içerik bütünlüğü dikkate alınarak "
            "tehdit suçunun somut olayda nasıl değerlendirileceği tartışıldı."
        ),
        tags=["Tehdit", "E-posta"],
        risk_level=RiskLevel.high,
        saved=False,
    ),
    PrecedentRecord(
        id="precedent-008",
        title="Yorum dizisinde hedef gösterme ve toplu saldırı çağrısı değerlendirmesi",
        court="Bursa 5. Asliye Ceza Mahkemesi",
        date="2024-08-15",
        summary=(
            "Kamuya açık yorum dizisinde mağdurun kullanıcı bilgileriyle hedef gösterilmesi "
            "ifade özgürlüğü sınırları dışında hukuka aykırılık olarak değerlendirildi."
        ),
        tags=["Hakaret", "Hedef gösterme"],
        risk_level=RiskLevel.high,
        saved=False,
    ),
]
