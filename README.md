# LawBridge Backend

FastAPI tabanlı LawBridge backend servisidir. Frontend tarafındaki `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api/v1` sözleşmesine uygun şekilde `/api/v1` altında analiz, sınıflandırma, emsal arama ve başvuru taslağı endpointleri sağlar.

## Modeller

Backend model ağırlıklarını repo içine koymaz. Modeller çalışma zamanında Hugging Face üzerinden indirilir ve Hugging Face'in kendi cache dizininde tutulur.

| Servis | Varsayılan Hugging Face repo |
| --- | --- |
| Sentiment | `lawbridge/sentiment-berturk` |
| Intent | `lawbridge/intent-berturk` |
| Legal | `lawbridge/lawbridge-legal-model` |
| Retrieval / semantic search | `lawbridge/turkish-legal-precedent-retrieval` |
| Karar dataseti | `Structured_Judgements` |

Gerekirse `.env` dosyasında bu repo id'lerini değiştirebilirsiniz:

```env
HF_TOKEN=
SENTIMENT_MODEL_PATH=lawbridge/sentiment-berturk
INTENT_MODEL_PATH=lawbridge/intent-berturk
LEGAL_MODEL_PATH=lawbridge/lawbridge-legal-model
RETRIEVAL_MODEL_PATH=lawbridge/turkish-legal-precedent-retrieval
```

Eski yerel klasör yapısını kullanmanız gerekirse `SENTIMENT_MODEL_PATH=models/...` gibi bir yerel path de verilebilir. Göreli yerel pathler backend proje köküne göre çözülür.

`Structured_Judgements` klasöründeki `vision_llm_processed_*.json` dosyaları otomatik okunur. Bu klasör yoksa backend eski 8 kayıtlık seed emsal listesini fallback olarak kullanır.

## YouTube Yorum Analizi

`/api/v1/analyze` endpointine `sourceType: "youtube-comment"` ve bir YouTube video linki gönderildiğinde backend video ID'sini çıkarır, YouTube Data API üzerinden üst seviye yorumları çeker ve her yorumu mevcut sentiment, intent ve legal modelleriyle analiz eder.

Bu özellik için `.env` içinde YouTube Data API anahtarı gerekir:

```bash
YOUTUBE_API_KEY=...
YOUTUBE_MAX_COMMENTS=25
```

API anahtarı yoksa YouTube linki verilen analizlerde backend açık bir hata döndürür. YouTube yorumu doğrudan metin olarak girilirse normal metin analizi gibi çalışır.

## Supabase / PostgreSQL

Kaydedilen analizler ve kullanıcı özeti varsayılan olarak Supabase Postgres'e yazılacak şekilde hazırlanmıştır. `.env` içinde `DATABASE_URL` veya `SUPABASE_DATABASE_URL` doluysa backend JSON dosyası yerine Postgres kullanır. Boş bırakılırsa eski `data/analyses.json` fallback'i çalışır.

Supabase Dashboard > Project Settings > Database bölümünden connection string alın ve `sslmode=require` ile ekleyin:

```env
DATABASE_URL=postgresql://postgres.<project-ref>:<password>@aws-0-eu-central-1.pooler.supabase.com:6543/postgres?sslmode=require
AUTO_CREATE_DB_TABLES=true
```

`AUTO_CREATE_DB_TABLES=true` ise backend ilk veritabanı işleminde `lawbridge_users` ve `lawbridge_analyses` tablolarını oluşturur. İsterseniz aynı şemayı Supabase SQL Editor içinde manuel çalıştırmak için `db/supabase_schema.sql` dosyasını kullanabilirsiniz.

Frontend ve mobil uygulama Firebase kullanıcı bilgisini backend'e `X-LawBridge-User-Id`, `X-LawBridge-User-Email` ve `X-LawBridge-User-Name` header'larıyla gönderir. Backend analizleri bu kullanıcı id'sine göre listeler, getirir ve siler.

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
| `GET` | `/api/v1/profile` | Giriş yapan kullanıcının profil bilgisini döndürür |
| `PUT` | `/api/v1/profile` | Profil bilgisini Postgres'e kaydeder |
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
