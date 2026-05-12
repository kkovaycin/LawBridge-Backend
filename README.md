# LawBridge Backend

FastAPI tabanlı LawBridge backend servisidir. Frontend tarafındaki `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api/v1` sözleşmesine uygun şekilde `/api/v1` altında analiz, sınıflandırma, emsal arama ve başvuru taslağı endpointleri sağlar.

## Modeller

Backend model dosyalarını repoya kopyalamaz. Verdiğiniz klasörler varsayılan olarak backend klasörünün kardeş dizinlerinde aranır:

| Servis | Varsayılan path |
| --- | --- |
| Sentiment | `../Sentiment/sentiment_berturk_model` |
| Intent | `../Intent/intent_berturk_model` |
| Legal | `../Legal/lawbridge_legal_model` |
| Reasoning / semantic search | `../MiniLM_weak_summary_to_reasoning_seed42_ep7_msl256` |
| Karar dataseti | `Structured_Judgements` |

Gerekirse `.env` dosyasında bu pathleri değiştirebilirsiniz.

`Structured_Judgements` klasöründeki `vision_llm_processed_*.json` dosyaları otomatik okunur. Bu klasör yoksa backend eski 8 kayıtlık seed emsal listesini fallback olarak kullanır.

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
