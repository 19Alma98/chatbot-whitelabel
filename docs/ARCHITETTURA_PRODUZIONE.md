# Architettura di Produzione - Agente RAG Chatbot Whitelabel

## 1. Executive Summary

Questo documento descrive l'architettura definitiva per mettere in produzione l'agente RAG basato su FastAPI, PostgreSQL con pgvector e Azure OpenAI. L'architettura segue le best practice per sistemi AI in produzione, con focus su scalabilità, osservabilità, sicurezza e resilienza.

**Stack Tecnologico Attuale:**
- Backend: FastAPI (Python 3.10+)
- Database: PostgreSQL con pgvector
- Vector Store: PostgreSQL pgvector / Azure AI Search (configurabile)
- LLM Provider: Azure OpenAI (gpt-4o-mini) # TODO: LLM provider è AzureOpenAi service con Azure Foundry 
- Embeddings: Azure OpenAI (text-embedding-ada-002) # TODO: embedding provider è AzureOpenAi service con Azure Foundry
- Autenticazione: Azure Managed Identity
- Monitoring: Azure Monitor + OpenTelemetry + LangSmith
- Deployment: Azure Container Apps # TODO: questo non è ancora definito

---

## 2. Architettura Generale

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend Layer                            │
│                    (React + FluentUI)                            │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTPS
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   API Gateway / Load Balancer                    │
│              (Azure Container Apps Ingress)                      │
└────────────────────────┬────────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
┌────────────────┐ ┌────────────────┐ ┌────────────────┐
│  FastAPI App   │ │  FastAPI App   │ │  FastAPI App   │
│   Instance 1   │ │   Instance 2   │ │   Instance N   │
└────────┬───────┘ └────────┬───────┘ └────────┬───────┘
         │                  │                  │
         └──────────────────┼──────────────────┘
                            │
         ┌──────────────────┼──────────────────┐
         ▼                  ▼                  ▼
┌──────────────────┐ ┌──────────────┐ ┌──────────────────┐
│   PostgreSQL     │ │ Azure OpenAI │ │ Azure AI Search  │
│  Flexible Server │ │              │ │   (Optional)     │
│   + pgvector     │ │ - Chat Model │ └──────────────────┘
│                  │ │ - Embeddings │
│ - Conversations  │ │              │
│ - Documents      │ └──────────────┘
│ - Vectors        │
└──────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────┐
│              Observability Stack                      │
│  - Azure Monitor (Application Insights)              │
│  - OpenTelemetry (Traces, Metrics, Logs)            │
│  - LangSmith (LLM Tracing & Evaluation)             │
│  - Log Analytics Workspace                           │
└──────────────────────────────────────────────────────┘
```

---

## 3. Componenti Core dell'Agente

### 3.1 RAG Engine (Doppia Modalità)

L'agente supporta due modalità di funzionamento:

#### **SimpleRAGChat**
- Flusso diretto: Query → Embedding → Vector Search → Context Assembly → LLM Response
- Ideale per: Query semplici, latenza critica, costi ridotti
- Use case: FAQ, ricerca documenti, Q&A dirette

#### **AdvancedRAGChat**
- Flusso avanzato: Query Rewriting → Function Calling → Filter Generation → Hybrid Search → Multi-step Reasoning
- Ideale per: Query complesse, analisi multi-documento, reasoning avanzato
- Use case: Analisi approfondite, query con filtri dinamici, conversazioni complesse

**File chiave:**
- `fastapi_app/rag_base.py` - Classe base astratta
- `fastapi_app/rag_simple.py` - Implementazione semplice
- `fastapi_app/rag_advanced.py` - Implementazione avanzata con function calling

### 3.2 Vector Store Layer (Configurabile)

**Opzione 1: PostgreSQL + pgvector** (Default)
- Vector storage nativo in PostgreSQL
- Hybrid search: Full-text search (PostgreSQL) + Vector similarity (pgvector)
- RRF (Reciprocal Rank Fusion) per combinare risultati
- Implementazione: `fastapi_app/postgres_searcher.py`

**Opzione 2: Azure AI Search**
- Vector search gestito
- Maggiore scalabilità per grandi volumi
- Integrazione nativa con Azure
- Implementazione: `fastapi_app/azure_ai_search_searcher.py`

**Configurazione:** Variabile d'ambiente `VECTOR_STORE` (PGVECTOR | AZURE_AI_SEARCH)

### 3.3 Conversation Service

Gestione della cronologia conversazionale persistente:
- Storage su PostgreSQL
- Tracking di conversation_id
- Metadata storage: chat_params, contextual_messages, document_ids, thoughts
- API per retrieval, listing, cancellazione conversazioni

**File:** `fastapi_app/conversation_service.py`

### 3.4 PDF Processing Pipeline

Sistema di ingestione documenti:
- Upload PDF tramite API
- Chunking intelligente con LangChain TextSplitters
- Generazione embeddings batch
- Storage in database con metadata

**File:** `fastapi_app/pdf_processor.py`

---

## 4. Best Practice per Produzione

### 4.1 Scalabilità e Performance

#### **Scaling Strategies**

**Horizontal Scaling (Raccomandato)**
```yaml
# Azure Container Apps - azure.yaml
resources:
  - type: Microsoft.App/containerApps
    properties:
      configuration:
        scale:
          minReplicas: 2
          maxReplicas: 10
          rules:
            - name: http-scaling
              http:
                metadata:
                  concurrentRequests: "50"
```

**Connection Pooling**
```python
# Già implementato in postgres_engine.py
engine = create_async_engine(
    connection_string,
    echo=False,
    pool_size=20,          # Aumentare per produzione
    max_overflow=10,       # Connection burst capacity
    pool_pre_ping=True,    # Health check delle connessioni
    pool_recycle=3600,     # Riciclo ogni ora
)
```

#### **Caching Strategy**

**Da implementare:** Redis per cache embeddings e risultati di ricerca frequenti

```python
# Pseudocodice - da aggiungere
import redis.asyncio as redis

class CachedEmbedder:
    def __init__(self, redis_client, openai_client):
        self.redis = redis_client
        self.openai = openai_client
    
    async def get_embedding(self, text: str):
        cache_key = f"emb:{hashlib.sha256(text.encode()).hexdigest()}"
        cached = await self.redis.get(cache_key)
        if cached:
            return json.loads(cached)
        
        embedding = await self.openai.embeddings.create(...)
        await self.redis.setex(cache_key, 86400, json.dumps(embedding))
        return embedding
```

**Benefici:**
- Riduzione costi API OpenAI del 40-60%
- Latenza ridotta per query ripetute
- Miglior user experience

### 4.2 Observability (Già Implementato ✓)

#### **Monitoring Stack Attuale**

**Azure Monitor + Application Insights**
```python
# __init__.py (già presente)
if os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
    configure_azure_monitor(logger_name="ragapp")
    OpenAIInstrumentor().instrument()
    SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
```

**LangSmith Integration** (già configurato)
- Tracing completo delle chiamate LLM
- Valutazione qualità risposte
- Debugging conversazioni problematiche
- Cost tracking per conversation

**OpenTelemetry** (strumentazione completa)
- Traces: Request flow end-to-end
- Metrics: Latency, throughput, error rates
- Logs: Structured logging con context

#### **KPI da Monitorare**

**Performance Metrics**
- P50/P95/P99 latency per endpoint `/chat` e `/chat/stream`
- Token usage per request (prompt + completion)
- Vector search latency
- Database query performance

**Business Metrics**
- Conversations created per day
- Average conversation length
- User satisfaction (da implementare con feedback API)
- Document retrieval accuracy

**System Health**
- API error rate (target: < 0.1%)
- Database connection pool utilization
- Container CPU/Memory usage
- OpenAI API rate limits hit count

### 4.3 Sicurezza

#### **Autenticazione e Autorizzazione**

**Attualmente Implementato:**
- Azure Managed Identity per accesso a servizi Azure
- No autenticazione utente (da implementare)

**Da Implementare per Produzione:**

```python
# Aggiungere middleware OAuth/JWT
from fastapi import Security, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    token = credentials.credentials
    # Validare con Azure AD / Auth0 / Custom
    if not validate_jwt(token):
        raise HTTPException(status_code=401, detail="Invalid token")
    return get_user_from_token(token)

# Proteggere endpoint
@router.post("/chat")
async def chat_handler(
    ...,
    current_user: User = Depends(verify_token)
):
    # Validare che l'utente abbia accesso alla conversation_id
    pass
```

**Row-Level Security per Conversazioni**

```sql
-- PostgreSQL RLS per isolare dati per tenant/utente
ALTER TABLE conversation_messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY user_conversations ON conversation_messages
    FOR ALL
    USING (user_id = current_setting('app.current_user_id')::INTEGER);
```

#### **Data Protection**

**Encryption at Rest** (già gestito da Azure)
- PostgreSQL: Automatic encryption
- Azure OpenAI: Dati non persistiti (per policy)
- Azure Storage: Encryption by default

**Encryption in Transit**
- TLS 1.2+ per tutte le connessioni
- Managed Identity elimina credenziali in chiaro

**Secrets Management**
- Azure Key Vault per segreti (se necessario)
- Attualmente: Managed Identity elimina necessità di API keys

#### **Content Safety**

**Già implementato:**
```python
# Content filtering di Azure OpenAI
if isinstance(error, APIError) and error.code == "content_filter":
    return ErrorResponse(error="Content flagged by filter")
```

**Da aggiungere:**
- Input validation più rigorosa
- Rate limiting per utente
- Anomaly detection per pattern di utilizzo sospetti

### 4.4 Resilienza e Error Handling

#### **Retry Logic con Exponential Backoff**

**Da implementare:**
```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from openai import RateLimitError, APITimeoutError

class ResilientRAGChat:
    @retry(
        retry=retry_if_exception_type((RateLimitError, APITimeoutError)),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        stop=stop_after_attempt(3),
    )
    async def call_openai_with_retry(self, **kwargs):
        return await self.openai_client.chat.completions.create(**kwargs)
```

#### **Circuit Breaker Pattern**

Per proteggere da fallimenti a cascata:
```python
from circuitbreaker import circuit

@circuit(failure_threshold=5, recovery_timeout=60)
async def call_vector_search(query: str):
    # Se fallisce 5 volte, apre il circuito per 60s
    return await searcher.search(query)
```

#### **Fallback Strategies**

```python
async def answer_with_fallback(self, query: str):
    try:
        # Tentativo con advanced flow
        return await self.advanced_rag.answer(query)
    except OpenAIError:
        logger.warning("Advanced flow failed, falling back to simple")
        return await self.simple_rag.answer(query)
    except Exception as e:
        logger.error(f"All RAG flows failed: {e}")
        return "Mi dispiace, il servizio è temporaneamente non disponibile."
```

#### **Health Checks**

**Da aggiungere endpoint:**
```python
@router.get("/health")
async def health_check(db_session: DBSession):
    checks = {
        "database": await check_database_health(db_session),
        "openai": await check_openai_health(),
        "vector_store": await check_vector_store_health(),
    }
    
    if all(checks.values()):
        return {"status": "healthy", "checks": checks}
    else:
        raise HTTPException(status_code=503, detail=checks)
```

### 4.5 Cost Optimization

#### **Token Management**

**Già implementato parzialmente:**
- Response token limit: 1024
- Token counting con `openai-messages-token-helper`

**Da ottimizzare:**
```python
# Implementare token budget per conversation
class ConversationTokenManager:
    MAX_CONTEXT_TOKENS = 4000
    
    async def trim_context_to_budget(self, messages, token_budget):
        """Mantieni solo messaggi più recenti che rientrano nel budget"""
        # Algoritmo: sliding window + summarization dei messaggi vecchi
        pass
```

#### **Embedding Caching**
Già discusso in 4.1 - può ridurre costi del 40-60%

#### **Model Selection Strategy**

```python
# Routing dinamico basato su complessità query
def select_model_for_query(query: str, complexity_score: float):
    if complexity_score < 0.3:
        return "gpt-3.5-turbo"  # Query semplici
    elif complexity_score < 0.7:
        return "gpt-4o-mini"    # Query medie (attuale default)
    else:
        return "gpt-4o"         # Query complesse
```

### 4.6 Database Management

#### **Indexing Strategy**

**Già presente:**
```sql
-- pgvector indexes
CREATE INDEX ON items USING hnsw (embedding_ada002 vector_cosine_ops);
CREATE INDEX ON items USING GIN (to_tsvector('english', description));
```

**Da aggiungere per conversazioni:**
```sql
-- Index per performance query conversazioni
CREATE INDEX idx_conv_messages_conv_id_timestamp 
    ON conversation_messages(conversation_id, created_at DESC);

CREATE INDEX idx_conv_messages_user_id 
    ON conversation_messages(user_id) 
    WHERE user_id IS NOT NULL;
```

#### **Backup Strategy**

**Azure PostgreSQL Flexible Server:**
- Backup automatici giornalieri (retention 7-35 giorni)
- Point-in-time restore
- Geo-redundancy per DR

**Raccomandazioni:**
- Retention: 30 giorni per produzione
- Test restore mensili
- Export settimanale dei dati critici

#### **Database Migration Management**

**Già implementato con Alembic:**
```bash
# Directory: /alembic

# Creare nuova migrazione
alembic revision --autogenerate -m "Add user_id to conversations"

# Applicare migrazioni
alembic upgrade head

# Rollback
alembic downgrade -1
```

**Best Practice:**
- Migrazioni atomiche
- Test su environment staging prima di prod
- Backup prima di ogni migrazione in produzione

---

## 5. Deployment Architecture

### 5.1 Azure Container Apps Setup

**Configurazione Produzione:**

```yaml
# infra/main.bicep (estratto concettuale)
resource containerApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: 'ragchatbot-app'
  properties:
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'http'
        corsPolicy: {
          allowedOrigins: ['https://yourdomain.com']
          allowedMethods: ['GET', 'POST', 'DELETE']
        }
      }
      secrets: [
        {
          name: 'applicationinsights-connection-string'
          value: applicationInsights.properties.ConnectionString
        }
      ]
      registries: [
        {
          server: containerRegistry.properties.loginServer
          identity: userAssignedIdentity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'ragchatbot'
          image: '${containerRegistry.properties.loginServer}/ragchatbot:latest'
          resources: {
            cpu: '1.0'
            memory: '2Gi'
          }
          env: [
            {
              name: 'RUNNING_IN_PRODUCTION'
              value: 'true'
            }
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              secretRef: 'applicationinsights-connection-string'
            }
            // ... altre env vars
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/health'
                port: 8000
              }
              initialDelaySeconds: 30
              periodSeconds: 10
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/health'
                port: 8000
              }
              initialDelaySeconds: 10
              periodSeconds: 5
            }
          ]
        }
      ]
      scale: {
        minReplicas: 2
        maxReplicas: 10
        rules: [
          {
            name: 'http-scaling-rule'
            http: {
              metadata: {
                concurrentRequests: '50'
              }
            }
          }
          {
            name: 'cpu-scaling-rule'
            custom: {
              type: 'cpu'
              metadata: {
                type: 'Utilization'
                value: '70'
              }
            }
          }
        ]
      }
    }
  }
}
```

### 5.2 Environment Variables (Produzione)

**Configurazione Completa:**

```bash
# Azure OpenAI
OPENAI_CHAT_HOST=azure
OPENAI_EMBED_HOST=azure
AZURE_OPENAI_ENDPOINT=https://<your-instance>.openai.azure.com
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4o-mini
AZURE_OPENAI_CHAT_MODEL=gpt-4o-mini
AZURE_OPENAI_EMBED_DEPLOYMENT=text-embedding-ada-002
AZURE_OPENAI_EMBED_MODEL=text-embedding-ada-002
AZURE_OPENAI_EMBED_DIMENSIONS=1536
AZURE_OPENAI_EMBEDDING_COLUMN=embedding_ada002

# Vector Store Configuration
VECTOR_STORE=PGVECTOR  # o AZURE_AI_SEARCH

# Azure AI Search (opzionale)
AZURE_SEARCH_ENDPOINT=https://<search-service>.search.windows.net
AZURE_SEARCH_INDEX=documents
# AZURE_SEARCH_API_KEY - non necessario con Managed Identity

# PostgreSQL
POSTGRES_HOST=<db-server>.postgres.database.azure.com
POSTGRES_DATABASE=chatbot
POSTGRES_USERNAME=<admin-user>
# Password gestita via Managed Identity

# Managed Identity
APP_IDENTITY_ID=<managed-identity-client-id>
AZURE_TENANT_ID=<tenant-id>

# Observability
APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=...
LANGSMITH_API_KEY=<your-langsmith-key>
LANGSMITH_PROJECT=ragchatbot-prod
LANGSMITH_WORKSPACE_ID=<workspace-id>

# Application
RUNNING_IN_PRODUCTION=true
LOG_LEVEL=INFO
```

### 5.3 CI/CD Pipeline

**GitHub Actions Workflow (concettuale):**

```yaml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run tests
        run: |
          pip install -r requirements.txt
          pytest tests/
      
      - name: Run linting
        run: |
          ruff check .
          mypy fastapi_app/

  build-and-deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Azure Login
        uses: azure/login@v1
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}
      
      - name: Build and push image
        run: |
          az acr build --registry <registry-name> \
            --image ragchatbot:${{ github.sha }} \
            --image ragchatbot:latest \
            --file Dockerfile .
      
      - name: Run database migrations
        run: |
          # Connettersi al DB e eseguire alembic upgrade
          alembic upgrade head
      
      - name: Deploy to Container Apps
        run: |
          az containerapp update \
            --name ragchatbot-app \
            --resource-group <rg-name> \
            --image <registry>.azurecr.io/ragchatbot:${{ github.sha }}
      
      - name: Run smoke tests
        run: |
          curl -f https://<app-url>/health || exit 1
```

---

## 6. Checklist Pre-Produzione

### ☐ Sicurezza
- [ ] Implementare autenticazione utente (OAuth2/JWT)
- [ ] Configurare Row-Level Security su PostgreSQL
- [ ] Abilitare Content Safety per input/output
- [ ] Implementare rate limiting per utente/IP
- [ ] Audit logging per azioni sensibili
- [ ] Penetration testing

### ☐ Performance
- [ ] Load testing con Locust (già presente: `locustfile.py`)
- [ ] Ottimizzare query database (EXPLAIN ANALYZE)
- [ ] Implementare caching Redis per embeddings
- [ ] Configurare CDN per static assets
- [ ] Connection pooling dimensionato correttamente
- [ ] Benchmark latency P95 < 2s per `/chat`

### ☐ Osservabilità
- [ ] Dashboard Application Insights configurato
- [ ] Alert su metriche critiche (error rate, latency)
- [ ] LangSmith tracing attivo e monitorato
- [ ] Log retention policy definita
- [ ] On-call rotation e runbook definiti

### ☐ Resilienza
- [ ] Health check endpoint implementato
- [ ] Retry logic con backoff esponenziale
- [ ] Circuit breaker per servizi esterni
- [ ] Graceful degradation strategy
- [ ] Disaster recovery plan testato
- [ ] Backup restore testato

### ☐ Costi
- [ ] Budget alert configurati su Azure
- [ ] Token usage monitoring attivo
- [ ] Embedding cache implementato
- [ ] Model selection strategy ottimizzata
- [ ] Right-sizing delle risorse (CPU/Memory)

### ☐ Compliance
- [ ] GDPR compliance: Right to deletion implementato
- [ ] Data residency requirements verificati
- [ ] Audit trail per accesso dati sensibili
- [ ] Terms of Service e Privacy Policy definiti

---

## 7. Monitoring Dashboard (KPI Principali)

### Dashboard Consigliato su Application Insights

**Sezione 1: User Experience**
- Request Rate (req/min)
- Average Response Time (P50, P95, P99)
- Error Rate (%)
- Active Conversations

**Sezione 2: AI Performance**
- OpenAI API Latency
- Token Usage (Prompt + Completion)
- Vector Search Latency
- Retrieval Accuracy (context relevance)

**Sezione 3: System Health**
- Container CPU/Memory Usage
- Database Connection Pool
- Active Requests
- Queue Depth (se implementato)

**Sezione 4: Costs**
- OpenAI API Cost per Day
- Database IOPS
- Egress Bandwidth
- Total Infrastructure Cost

**Alert Rules:**
```kusto
// Error rate > 5% in 5 minutes
requests
| where timestamp > ago(5m)
| summarize 
    total = count(),
    errors = countif(success == false)
| extend errorRate = errors * 100.0 / total
| where errorRate > 5

// P95 latency > 3s
requests
| where timestamp > ago(15m)
| where name == "POST /chat"
| summarize p95 = percentile(duration, 95)
| where p95 > 3000

// OpenAI token usage spike
dependencies
| where target contains "openai"
| where timestamp > ago(1h)
| extend tokens = toint(customDimensions.total_tokens)
| summarize totalTokens = sum(tokens)
| where totalTokens > 1000000  // 1M tokens/hour threshold
```

---

## 8. Scaling Roadmap

### Phase 1: MVP in Produzione (Attuale)
- ✓ Single region deployment
- ✓ 2-5 replicas
- ✓ PostgreSQL pgvector
- ✓ Basic monitoring

### Phase 2: Optimization (1-3 mesi)
- [ ] Redis caching layer
- [ ] Advanced rate limiting
- [ ] User authentication
- [ ] Enhanced error handling
- [ ] Cost optimization implementata

### Phase 3: Scale (3-6 mesi)
- [ ] Multi-region deployment
- [ ] Azure AI Search per vector store
- [ ] Dedicated embedding service
- [ ] Advanced analytics e A/B testing
- [ ] Custom fine-tuned models

### Phase 4: Enterprise (6-12 mesi)
- [ ] Multi-tenancy completo
- [ ] Dedicated deployments per cliente
- [ ] Advanced security (HSM, private endpoints)
- [ ] SLA garantiti (99.9%)
- [ ] White-label completo per cliente

---

## 9. Costi Stimati (Produzione Base)

**Assunzioni:**
- 10,000 conversazioni/mese
- 10 messaggi/conversazione media
- 500 token/messaggio medio (prompt + completion)

### Breakdown Costi Mensili

| Servizio | Dimensionamento | Costo Mensile (USD) |
|----------|----------------|---------------------|
| **Azure Container Apps** | 2-5 replicas, 1vCPU, 2GB RAM | $150-300 |
| **PostgreSQL Flexible Server** | Standard_B2s (2vCPU, 4GB) | $120 |
| **Azure OpenAI** | 50M tokens/mese | $100-150 |
| **Azure Monitor** | Log Analytics + App Insights | $50-100 |
| **Azure Storage** | Backup, logs | $20 |
| **Networking** | Egress data | $30 |
| **Total** | | **$470-720/mese** |

**Note:**
- Costi OpenAI possono variare significativamente con volume
- Implementare caching può ridurre costi OpenAI del 40-60%
- Scaling automatico ottimizza costi Container Apps

---

## 10. Contatti e Risorse

### Documentazione Tecnica
- [FastAPI Official Docs](https://fastapi.tiangolo.com/)
- [Azure OpenAI Service](https://learn.microsoft.com/azure/ai-services/openai/)
- [pgvector Documentation](https://github.com/pgvector/pgvector)
- [Azure Container Apps](https://learn.microsoft.com/azure/container-apps/)

### Monitoring & Debugging
- Application Insights: `https://portal.azure.com`
- LangSmith Dashboard: Configurato con LANGSMITH_PROJECT
- Log Analytics: Query Kusto per deep dive

### Support Runbook
**Incident Response:**
1. Check Application Insights per error spike
2. Review recent deployments (rollback se necessario)
3. Check Azure Service Health
4. Review LangSmith traces per conversazioni fallite
5. Scale manualmente se sotto load

**Common Issues:**
- **High latency**: Check OpenAI API status, database query performance
- **Errori 429**: Rate limit OpenAI → implement exponential backoff
- **Database connection errors**: Check connection pool saturation
- **Memory leaks**: Monitor container memory, restart se necessario

---

## 11. Conclusioni

Questa architettura fornisce una base solida per un sistema RAG in produzione, con:

✅ **Scalabilità**: Horizontal scaling automatico su Container Apps  
✅ **Osservabilità**: Monitoring completo con Azure Monitor, OpenTelemetry, LangSmith  
✅ **Sicurezza**: Managed Identity, encryption at rest/in transit  
✅ **Resilienza**: Health checks, retry logic, fallback strategies  
✅ **Flessibilità**: Vector store configurabile (pgvector/AI Search), modalità RAG multiple

**Prossimi Step Raccomandati:**
1. Implementare autenticazione utente e RLS
2. Aggiungere Redis caching per embeddings
3. Configurare alert e dashboard su Application Insights
4. Load testing con 10x traffico previsto
5. Disaster recovery drill

---

**Documento creato:** 2025-11-24  
**Versione:** 1.0  
**Autore:** AI Architecture Review

