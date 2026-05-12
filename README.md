# LawBridge Backend

FastAPI tabanlı LawBridge backend servisidir. Frontend tarafındaki `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api/v1` sözleşmesine uygun şekilde `/api/v1` altında analiz, sınıflandırma, emsal arama ve başvuru taslağı endpointleri sağlar.

## Modeller

Backend model dosyalarını proje içindeki `models/` klasöründen okur. Bu repo GitHub'a model ağırlıklarıyla gönderilecekse Git LFS kullanılmalıdır.

| Servis | Varsayılan path |
| --- | --- |
| Sentiment | `models/sentiment_berturk_model` |
| Intent | `models/intent_berturk_model` |
| Legal | `models/lawbridge_legal_model` |
| Reasoning / semantic search | `models/MiniLM_weak_summary_to_reasoning_seed42_ep7_msl256` |
| Karar dataseti | `Structured_Judgements` |

Gerekirse `.env` dosyasında bu pathleri değiştirebilirsiniz. `.env` içindeki göreli pathler backend proje köküne göre çözülür.

Git LFS ayarı `.gitattributes` içinde model ağırlıkları için tanımlıdır. Yeni bir bilgisayarda ilk kez çalışırken:

```bash
git lfs install
git lfs pull
```

`Structured_Judgements` klasöründeki `vision_llm_processed_*.json` dosyaları otomatik okunur. Bu klasör yoksa backend eski 8 kayıtlık seed emsal listesini fallback olarak kullanır.

## YouTube Yorum Analizi

`/api/v1/analyze` endpointine `sourceType: "youtube-comment"` ve bir YouTube video linki gönderildiğinde backend video ID'sini çıkarır, YouTube Data API üzerinden üst seviye yorumları çeker ve her yorumu mevcut sentiment, intent ve legal modelleriyle analiz eder.

Bu özellik için `.env` içinde YouTube Data API anahtarı gerekir:

```bash
YOUTUBE_API_KEY=...
YOUTUBE_MAX_COMMENTS=25
```

API anahtarı yoksa YouTube linki verilen analizlerde backend açık bir hata döndürür. YouTube yorumu doğrudan metin olarak girilirse normal metin analizi gibi çalışır.

## Kurulum

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
copy .env.example .env
```

Test araçlarını da kurmak için:

```bash
python -m pip install -r requirements-dev.txt
```

## Çalıştırma

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Swagger dokümantasyonu:

```text
http://127.0.0.1:8000/docs
```

## Ana Endpointler

| Method | Endpoint | Açıklama |
| --- | --- | --- |
| `GET` | `/api/v1/health` | Servis ve model path durumu |
| `GET` | `/api/v1/models` | Model etiketleri, path ve yüklenme durumu |
| `POST` | `/api/v1/analyze` | Dört modeli kullanarak birleşik hukuki analiz üretir |
| `GET` | `/api/v1/analyses` | Kaydedilmiş analizleri listeler |
| `GET` | `/api/v1/analyses/{id}` | Tek analiz döndürür |
| `DELETE` | `/api/v1/analyses/{id}` | Analizi siler |
| `POST` | `/api/v1/classify/sentiment` | Sentiment modeli |
| `POST` | `/api/v1/classify/intent` | Intent modeli |
| `POST` | `/api/v1/classify/legal` | Legal modeli |
| `GET` | `/api/v1/precedents` | Emsal kayıtları listeler |
| `GET` | `/api/v1/precedents/{id}` | Tek emsal kaydı |
| `POST` | `/api/v1/precedents/search` | SentenceTransformer ile semantik emsal araması |
| `POST` | `/api/v1/applications/draft` | Analizden basit başvuru/taslak metni üretir |

## Örnek Analiz İsteği

```bash
curl -X POST http://127.0.0.1:8000/api/v1/analyze ^
  -H "Content-Type: application/json" ^
  -d "{\"text\":\"Bu kişi beni herkese açık şekilde tehdit etti.\",\"sourceType\":\"text-comment\",\"save\":true}"
```

`/api/v1/analyze` yanıtında hem frontend kartına doğrudan verilebilecek `result` objesi hem de ham model çıktıları `classifications` altında döner.
