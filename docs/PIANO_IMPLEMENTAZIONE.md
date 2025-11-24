# Piano di Implementazione - Quick Wins per Produzione

## Priorità di Implementazione (MoSCoW)

### 🔴 MUST HAVE (Blocker per produzione)

#### 1. Health Check Endpoint (2 ore)
**Perché:** Container orchestration richiede health checks per restart automatici

```python
# Aggiungere a fastapi_app/routes/api_routes.py

@router.get("/health")
async def health_check(
    database_session: DBSession,
    openai_chat: ChatClient,
) -> dict[str, Any]:
    """Health check endpoint per Azure Container Apps liveness/readiness probes"""
    checks = {}
    overall_healthy = True
    
    # Check database
    try:
        await database_session.execute(text("SELECT 1"))
        checks["database"] = "healthy"
    except Exception as e:
        checks["database"] = f"unhealthy: {str(e)}"
        overall_healthy = False
    
    # Check OpenAI (lightweight - solo client ready)
    try:
        if openai_chat.client:
            checks["openai"] = "healthy"
        else:
            checks["openai"] = "unhealthy: client not initialized"
            overall_healthy = False
    except Exception as e:
        checks["openai"] = f"unhealthy: {str(e)}"
        overall_healthy = False
    
    status_code = 200 if overall_healthy else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if overall_healthy else "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": checks,
            "version": os.getenv("APP_VERSION", "unknown")
        }
    )

@router.get("/readiness")
async def readiness_check() -> dict[str, str]:
    """Lightweight readiness check"""
    return {"status": "ready"}
```

**Configurare in Azure Container Apps:**
```yaml
probes:
  - type: Liveness
    httpGet:
      path: /health
      port: 8000
    initialDelaySeconds: 30
    periodSeconds: 10
    failureThreshold: 3
  
  - type: Readiness
    httpGet:
      path: /readiness
      port: 8000
    initialDelaySeconds: 10
    periodSeconds: 5
```

---

#### 2. Retry Logic per OpenAI (4 ore)

**Perché:** OpenAI ha rate limits e timeout intermittenti

```python
# Creare nuovo file: fastapi_app/resilience.py

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
import logging
from openai import RateLimitError, APITimeoutError, APIConnectionError

logger = logging.getLogger("ragapp")

def create_openai_retry_decorator():
    """
    Retry decorator per chiamate OpenAI con exponential backoff
    
    Strategia:
    - Max 3 tentativi
    - Wait: 2^attempt secondi (2s, 4s, 8s)
    - Retry solo su errori transienti
    """
    return retry(
        retry=retry_if_exception_type((
            RateLimitError,
            APITimeoutError, 
            APIConnectionError
        )),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )

# Applicare a rag_simple.py e rag_advanced.py
class SimpleRAGChat(RAGChatBase):
    @create_openai_retry_decorator()
    async def _call_openai_with_retry(
        self, 
        messages: list[ChatCompletionMessageParam],
        **kwargs
    ) -> ChatCompletion:
        """Wrapped OpenAI call con retry logic"""
        return await self.openai_chat_client.chat.completions.create(
            model=self.chat_deployment or self.chat_model,
            messages=messages,
            **kwargs
        )
    
    async def answer(self, ...):
        # Sostituire chiamata diretta con versione retry
        response = await self._call_openai_with_retry(
            messages=contextual_messages,
            temperature=chat_params.temperature,
            ...
        )
```

**Modifiche a fare:**
1. Creare `fastapi_app/resilience.py`
2. Modificare `rag_simple.py` per usare retry wrapper
3. Modificare `rag_advanced.py` per usare retry wrapper
4. Aggiungere `tenacity` a `pyproject.toml` dependencies

---

#### 3. Rate Limiting (3 ore)

**Perché:** Protezione da abusi e controllo costi

```python
# Installare: pip install slowapi
# Aggiungere a pyproject.toml: slowapi>=0.1.9

# Modificare fastapi_app/__init__.py

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

def create_app(testing: bool = False) -> fastapi.FastAPI:
    # ... setup esistente ...
    
    # Rate limiter configuration
    limiter = Limiter(
        key_func=get_remote_address,  # Per utente autenticato: cambiare con get_user_id
        default_limits=["100/hour", "20/minute"]
    )
    
    app = fastapi.FastAPI(docs_url="/docs", lifespan=lifespan)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    
    # ... resto setup ...
    return app

# In api_routes.py applicare limiti specifici
from slowapi import Limiter
from fastapi import Request

@router.post("/chat")
@limiter.limit("30/minute")  # Max 30 chat al minuto per IP
async def chat_handler(
    request: Request,
    ...
):
    pass

@router.post("/upload-pdf")
@limiter.limit("5/hour")  # Max 5 upload/ora per IP
async def upload_pdf(request: Request, ...):
    pass
```

**Limiti Consigliati:**
- `/chat`: 30 richieste/minuto per utente
- `/upload-pdf`: 5 upload/ora per utente
- `/search`: 60 richieste/minuto per utente
- Global: 1000 richieste/ora per IP

---

#### 4. Logging Strutturato (2 ore)

**Perché:** Debugging efficace in produzione

```python
# Modificare fastapi_app/__init__.py

import json
import logging
from pythonjsonlogger import jsonlogger

def setup_structured_logging():
    """Setup JSON structured logging per Azure Monitor"""
    
    class CustomJsonFormatter(jsonlogger.JsonFormatter):
        def add_fields(self, log_record, record, message_dict):
            super().add_fields(log_record, record, message_dict)
            log_record['timestamp'] = datetime.utcnow().isoformat()
            log_record['level'] = record.levelname
            log_record['logger'] = record.name
            if hasattr(record, 'conversation_id'):
                log_record['conversation_id'] = record.conversation_id
            if hasattr(record, 'user_id'):
                log_record['user_id'] = record.user_id
    
    handler = logging.StreamHandler()
    formatter = CustomJsonFormatter(
        '%(timestamp)s %(level)s %(name)s %(message)s'
    )
    handler.setFormatter(formatter)
    
    logger = logging.getLogger("ragapp")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

def create_app(testing: bool = False) -> fastapi.FastAPI:
    if os.getenv("RUNNING_IN_PRODUCTION"):
        setup_structured_logging()
    else:
        logging.basicConfig(level=logging.INFO)
    # ... resto ...

# Usare logging con context:
logger.info(
    "Chat request processed",
    extra={
        "conversation_id": conversation_id,
        "tokens_used": response.usage.total_tokens,
        "latency_ms": latency,
        "retrieval_mode": chat_params.retrieval_mode,
    }
)
```

**Aggiungere a pyproject.toml:**
```toml
dependencies = [
    # ... existing ...
    "python-json-logger>=2.0.7",
]
```

---

#### 5. Environment Variables Validation (1 ora)

**Perché:** Fallimento veloce se configurazione errata

```python
# Creare: fastapi_app/config.py

from pydantic_settings import BaseSettings
from pydantic import Field, validator

class AppSettings(BaseSettings):
    """Validazione completa environment variables"""
    
    # OpenAI
    openai_chat_host: str = Field(..., env="OPENAI_CHAT_HOST")
    openai_embed_host: str = Field(..., env="OPENAI_EMBED_HOST")
    azure_openai_endpoint: str = Field(..., env="AZURE_OPENAI_ENDPOINT")
    azure_openai_chat_deployment: str = Field(..., env="AZURE_OPENAI_CHAT_DEPLOYMENT")
    
    # Database
    postgres_host: str = Field(..., env="POSTGRES_HOST")
    postgres_database: str = Field(..., env="POSTGRES_DATABASE")
    postgres_username: str = Field(..., env="POSTGRES_USERNAME")
    
    # Observability
    applicationinsights_connection_string: str | None = Field(
        None, 
        env="APPLICATIONINSIGHTS_CONNECTION_STRING"
    )
    
    # Application
    running_in_production: bool = Field(False, env="RUNNING_IN_PRODUCTION")
    log_level: str = Field("INFO", env="LOG_LEVEL")
    
    @validator("openai_chat_host", "openai_embed_host")
    def validate_openai_host(cls, v):
        if v not in ["azure", "openai", "ollama"]:
            raise ValueError("Must be one of: azure, openai, ollama")
        return v
    
    @validator("log_level")
    def validate_log_level(cls, v):
        if v not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            raise ValueError("Invalid log level")
        return v
    
    class Config:
        case_sensitive = False

# In __init__.py
def create_app(testing: bool = False) -> fastapi.FastAPI:
    # Validare config all'avvio
    try:
        settings = AppSettings()
        logger.info("Configuration validated successfully")
    except Exception as e:
        logger.error(f"Configuration validation failed: {e}")
        raise
    
    # ... resto app setup ...
```

---

### 🟡 SHOULD HAVE (Importante per stabilità)

#### 6. Graceful Shutdown (2 ore)

```python
# Modificare fastapi_app/__init__.py

import signal
import asyncio

shutdown_event = asyncio.Event()

def handle_shutdown_signal(signum, frame):
    """Handle SIGTERM da container orchestrator"""
    logger.info(f"Received signal {signum}, initiating graceful shutdown")
    shutdown_event.set()

@asynccontextmanager
async def lifespan(app: fastapi.FastAPI) -> AsyncIterator[State]:
    # Setup
    context = await common_parameters()
    engine = await create_postgres_engine_from_env(azure_credential)
    # ... altri setup ...
    
    yield state
    
    # Cleanup
    logger.info("Starting graceful shutdown...")
    
    # 1. Stop accepting new requests (gestito da FastAPI)
    # 2. Attendere completion richieste in corso (max 30s)
    try:
        await asyncio.wait_for(
            asyncio.shield(asyncio.sleep(0)),  # Placeholder per richieste attive
            timeout=30
        )
    except asyncio.TimeoutError:
        logger.warning("Shutdown timeout exceeded, forcing close")
    
    # 3. Chiudere connessioni database
    await engine.dispose()
    logger.info("Database connections closed")
    
    # 4. Flush logs
    logging.shutdown()

def create_app(testing: bool = False) -> fastapi.FastAPI:
    # ... setup ...
    
    # Registrare signal handlers
    signal.signal(signal.SIGTERM, handle_shutdown_signal)
    signal.signal(signal.SIGINT, handle_shutdown_signal)
    
    # ... resto ...
```

---

#### 7. Connection Pool Tuning (1 ora)

```python
# Modificare fastapi_app/postgres_engine.py

async def create_postgres_engine_from_env(
    azure_credential: AzureDeveloperCliCredential | ManagedIdentityCredential | None = None,
) -> AsyncEngine:
    # ... connessione esistente ...
    
    # Calcolare pool size basato su workload
    max_concurrent_requests = int(os.getenv("MAX_CONCURRENT_REQUESTS", "50"))
    # Regola: pool_size = (max_concurrent_requests / num_replicas) * 1.2
    pool_size = max(10, min(max_concurrent_requests // 2, 30))
    max_overflow = pool_size // 2
    
    engine = create_async_engine(
        connection_string,
        echo=False,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,  # Health check connessioni
        pool_recycle=3600,   # Ricicla ogni ora
        pool_timeout=30,     # Timeout acquisizione connessione
        connect_args={
            "server_settings": {
                "application_name": "ragchatbot",
                "statement_timeout": "30000",  # 30s query timeout
            },
            "command_timeout": 30,
        },
    )
    
    logger.info(
        f"Database engine created with pool_size={pool_size}, "
        f"max_overflow={max_overflow}"
    )
    
    return engine
```

**Aggiungere environment variable:**
```bash
MAX_CONCURRENT_REQUESTS=50  # Basato su container scaling rules
```

---

#### 8. Request Timeout Middleware (1 ora)

```python
# Creare: fastapi_app/middleware.py

import asyncio
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import time

class TimeoutMiddleware(BaseHTTPMiddleware):
    """Middleware per timeout globale su richieste"""
    
    def __init__(self, app, timeout_seconds: int = 60):
        super().__init__(app)
        self.timeout_seconds = timeout_seconds
    
    async def dispatch(self, request: Request, call_next):
        # Skip timeout per streaming endpoints
        if request.url.path.endswith("/stream"):
            return await call_next(request)
        
        try:
            return await asyncio.wait_for(
                call_next(request),
                timeout=self.timeout_seconds
            )
        except asyncio.TimeoutError:
            logger.error(
                f"Request timeout after {self.timeout_seconds}s",
                extra={"path": request.url.path, "method": request.method}
            )
            return JSONResponse(
                status_code=504,
                content={
                    "error": "Request timeout",
                    "message": f"Request took longer than {self.timeout_seconds}s"
                }
            )

# In __init__.py
def create_app(testing: bool = False) -> fastapi.FastAPI:
    app = fastapi.FastAPI(docs_url="/docs", lifespan=lifespan)
    
    # Add timeout middleware
    app.add_middleware(
        TimeoutMiddleware,
        timeout_seconds=int(os.getenv("REQUEST_TIMEOUT", "60"))
    )
    
    # ... resto ...
```

---

#### 9. Metrics Endpoint (2 ore)

```python
# Aggiungere a api_routes.py

from collections import defaultdict
import time

# Metrics storage (in produzione usare Redis o Prometheus)
metrics = defaultdict(lambda: {"count": 0, "total_time": 0, "errors": 0})

@router.get("/metrics")
async def get_metrics() -> dict[str, Any]:
    """Expose application metrics per monitoring"""
    
    # Calcolare statistiche
    stats = {}
    for endpoint, data in metrics.items():
        count = data["count"]
        if count > 0:
            stats[endpoint] = {
                "requests": count,
                "avg_latency_ms": round(data["total_time"] / count * 1000, 2),
                "error_rate": round(data["errors"] / count * 100, 2),
            }
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "uptime_seconds": time.time() - app_start_time,
        "endpoints": stats,
    }

# Aggiungere decoratore alle route
from functools import wraps

def track_metrics(endpoint_name: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                metrics[endpoint_name]["count"] += 1
                metrics[endpoint_name]["total_time"] += time.time() - start
                return result
            except Exception as e:
                metrics[endpoint_name]["errors"] += 1
                raise
        return wrapper
    return decorator

@router.post("/chat")
@track_metrics("chat")
async def chat_handler(...):
    pass
```

---

### 🟢 COULD HAVE (Nice to have)

#### 10. Redis Caching per Embeddings (6 ore)

```python
# Installare: pip install redis
# Aggiungere a pyproject.toml: redis>=5.0.0

# Creare: fastapi_app/cache.py

import redis.asyncio as redis
import hashlib
import json
from typing import Optional

class EmbeddingCache:
    """Cache Redis per embeddings"""
    
    def __init__(self, redis_url: str, ttl: int = 86400):
        self.redis = redis.from_url(redis_url, decode_responses=True)
        self.ttl = ttl  # 24 ore default
    
    def _get_cache_key(self, text: str, model: str) -> str:
        """Genera cache key da testo + model"""
        content = f"{model}:{text}"
        hash_key = hashlib.sha256(content.encode()).hexdigest()
        return f"emb:{hash_key}"
    
    async def get(self, text: str, model: str) -> Optional[list[float]]:
        """Recupera embedding da cache"""
        key = self._get_cache_key(text, model)
        cached = await self.redis.get(key)
        if cached:
            return json.loads(cached)
        return None
    
    async def set(self, text: str, model: str, embedding: list[float]) -> None:
        """Salva embedding in cache"""
        key = self._get_cache_key(text, model)
        await self.redis.setex(
            key,
            self.ttl,
            json.dumps(embedding)
        )
    
    async def close(self):
        await self.redis.close()

# Modificare embeddings.py per usare cache
class CachedEmbedder:
    def __init__(
        self, 
        openai_client, 
        cache: Optional[EmbeddingCache] = None
    ):
        self.client = openai_client
        self.cache = cache
    
    async def create_embedding(
        self, 
        text: str, 
        model: str,
        **kwargs
    ) -> list[float]:
        # Try cache first
        if self.cache:
            cached = await self.cache.get(text, model)
            if cached:
                logger.debug("Embedding cache hit")
                return cached
        
        # Generate embedding
        response = await self.client.embeddings.create(
            input=text,
            model=model,
            **kwargs
        )
        embedding = response.data[0].embedding
        
        # Cache result
        if self.cache:
            await self.cache.set(text, model, embedding)
        
        return embedding

# Aggiungere Redis URL a env vars:
# REDIS_URL=redis://localhost:6379/0
```

**Setup Redis su Azure:**
```bash
# Creare Azure Cache for Redis (Basic tier per development)
az redis create \
  --name ragchatbot-cache \
  --resource-group <rg-name> \
  --location <region> \
  --sku Basic \
  --vm-size c0  # 250MB cache
```

**Risparmio stimato:**
- Embedding cache hit rate: 40-50%
- Risparmio costi OpenAI: $50-80/mese
- Riduzione latenza: 200-300ms per richiesta

---

#### 11. A/B Testing Framework (4 ore)

```python
# Creare: fastapi_app/ab_testing.py

import hashlib
from enum import Enum

class ExperimentVariant(str, Enum):
    CONTROL = "control"
    VARIANT_A = "variant_a"
    VARIANT_B = "variant_b"

class ABTestManager:
    """Simple A/B testing per RAG configurations"""
    
    def __init__(self):
        self.experiments = {
            "rag_mode_test": {
                "variants": {
                    ExperimentVariant.CONTROL: {"use_advanced_flow": False},
                    ExperimentVariant.VARIANT_A: {"use_advanced_flow": True},
                },
                "traffic_split": {
                    ExperimentVariant.CONTROL: 0.5,
                    ExperimentVariant.VARIANT_A: 0.5,
                }
            }
        }
    
    def get_variant(self, experiment_id: str, user_id: str) -> ExperimentVariant:
        """Determina variant per utente (consistent hashing)"""
        experiment = self.experiments.get(experiment_id)
        if not experiment:
            return ExperimentVariant.CONTROL
        
        # Hash user_id per assignment consistente
        hash_value = int(hashlib.md5(
            f"{experiment_id}:{user_id}".encode()
        ).hexdigest(), 16)
        
        percentile = (hash_value % 100) / 100.0
        
        cumulative = 0.0
        for variant, traffic in experiment["traffic_split"].items():
            cumulative += traffic
            if percentile < cumulative:
                return variant
        
        return ExperimentVariant.CONTROL
    
    def get_config(self, experiment_id: str, variant: ExperimentVariant) -> dict:
        """Ottieni configurazione per variant"""
        experiment = self.experiments.get(experiment_id, {})
        return experiment.get("variants", {}).get(
            variant, 
            experiment["variants"][ExperimentVariant.CONTROL]
        )

# In api_routes.py
ab_test_manager = ABTestManager()

@router.post("/chat")
async def chat_handler(
    ...,
    user_id: str,  # Da autenticazione
):
    # Determinare variant
    variant = ab_test_manager.get_variant("rag_mode_test", user_id)
    config = ab_test_manager.get_config("rag_mode_test", variant)
    
    # Override settings con A/B test config
    chat_request.context.overrides.use_advanced_flow = config["use_advanced_flow"]
    
    # Log variant per analisi
    logger.info(
        "A/B test assignment",
        extra={
            "user_id": user_id,
            "experiment": "rag_mode_test",
            "variant": variant,
        }
    )
    
    # ... resto handler ...
```

---

## Timeline di Implementazione

### Sprint 1: Must Have (1 settimana)
```
Giorno 1-2:
✅ Task 1: Health check endpoint
✅ Task 5: Environment validation

Giorno 3-4:
✅ Task 2: Retry logic OpenAI
✅ Task 4: Structured logging

Giorno 5:
✅ Task 3: Rate limiting
✅ Testing integrazione
```

### Sprint 2: Should Have (1 settimana)
```
Giorno 1-2:
✅ Task 6: Graceful shutdown
✅ Task 7: Connection pool tuning

Giorno 3-4:
✅ Task 8: Request timeout
✅ Task 9: Metrics endpoint

Giorno 5:
✅ Testing carico
✅ Documentazione
```

### Sprint 3: Could Have (Opzionale - 1-2 settimane)
```
Settimana 1:
✅ Task 10: Redis caching (alta priorità per ROI)

Settimana 2:
✅ Task 11: A/B testing framework
✅ Ottimizzazioni varie
```

---

## Testing Plan

### Load Testing con Locust

```python
# Modificare locustfile.py esistente

from locust import HttpUser, task, between
import json

class ChatbotUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        """Setup per user"""
        self.conversation_id = None
    
    @task(10)
    def chat_simple(self):
        """Test chat endpoint - query semplice"""
        response = self.client.post(
            "/chat",
            json={
                "messages": [{"role": "user", "content": "What is climbing gear?"}],
                "context": {
                    "overrides": {
                        "use_advanced_flow": False,
                        "retrieval_mode": "hybrid",
                        "top": 3,
                    }
                },
                "conversation_id": self.conversation_id,
            }
        )
        if response.ok:
            data = response.json()
            if not self.conversation_id:
                # Estrarre conversation_id dalla prima risposta
                pass
    
    @task(5)
    def chat_advanced(self):
        """Test chat endpoint - query complessa"""
        self.client.post(
            "/chat",
            json={
                "messages": [{
                    "role": "user", 
                    "content": "Show me climbing ropes under $50"
                }],
                "context": {
                    "overrides": {"use_advanced_flow": True}
                },
            }
        )
    
    @task(2)
    def search(self):
        """Test search endpoint"""
        self.client.get("/search?query=climbing&top=5")
    
    @task(1)
    def health_check(self):
        """Test health endpoint"""
        self.client.get("/health")

# Run test:
# locust -f locustfile.py --host=http://localhost:8000 --users=50 --spawn-rate=5
```

**Target Performance:**
- P95 latency < 2000ms per `/chat`
- P99 latency < 4000ms per `/chat`
- Error rate < 0.5%
- Throughput > 100 req/s (per replica)

---

## Monitoring Alerts (Azure Monitor)

### Alert Rules da Configurare

```kusto
// 1. High Error Rate
let threshold = 5.0;
requests
| where timestamp > ago(5m)
| summarize 
    total = count(),
    errors = countif(success == false)
| extend errorRate = (errors * 100.0) / total
| where errorRate > threshold
| project 
    timestamp = now(),
    errorRate,
    errors,
    total

// 2. High Latency
let threshold = 3000; // 3 secondi
requests
| where timestamp > ago(10m)
| where name == "POST /chat"
| summarize p95 = percentile(duration, 95) by bin(timestamp, 5m)
| where p95 > threshold

// 3. OpenAI Token Spike
let threshold = 500000; // 500k tokens in 1h
dependencies
| where target contains "openai"
| where timestamp > ago(1h)
| extend tokens = toint(customDimensions["total_tokens"])
| summarize totalTokens = sum(tokens)
| where totalTokens > threshold

// 4. Database Connection Pool Exhaustion
traces
| where message contains "pool" and message contains "timeout"
| where timestamp > ago(10m)
| summarize count() by bin(timestamp, 5m)
| where count_ > 10

// 5. High Memory Usage (richiede metrics da container)
// Configurare in Azure Container Apps monitoring
```

**Azioni Alert:**
- Email a team
- SMS per critical alerts
- Webhook a Slack/Teams
- Auto-scale trigger (se possibile)

---

## Deployment Checklist

### Pre-Deployment
- [ ] Tutti i test passano (unit + integration)
- [ ] Load test completato con successo
- [ ] Linting pulito (ruff + mypy)
- [ ] Environment variables validate in staging
- [ ] Database migrations testate
- [ ] Backup database eseguito
- [ ] Rollback plan documentato

### Deployment
- [ ] Blue-green deployment o canary release
- [ ] Health checks passano su nuova versione
- [ ] Smoke tests passano
- [ ] Monitoring attivo e funzionante
- [ ] Alert configurati e testati

### Post-Deployment
- [ ] Monitor error rate per 1h
- [ ] Verificare latency metrics
- [ ] Controllare costi Azure/OpenAI
- [ ] Review logs per warning inaspettati
- [ ] Comunicare successo a stakeholders

---

## Costi Addizionali Implementazione

| Componente | Costo Incrementale/Mese |
|------------|------------------------|
| Redis Cache (Basic C0) | $15-20 |
| Monitoring aggiuntivo | $10-20 |
| Load testing (dev) | $0 (Locust open source) |
| **Risparmio da caching** | **-$50 a -$80** |
| **Net Impact** | **-$5 a -$35** (risparmio) |

**ROI:** Implementazione Redis caching paga se stessa in < 1 mese

---

## Risorse Aggiuntive

### Scripts Utili

```bash
# Script: scripts/check_production_readiness.sh
#!/bin/bash

echo "🔍 Checking production readiness..."

# Check environment variables
required_vars=(
    "AZURE_OPENAI_ENDPOINT"
    "POSTGRES_HOST"
    "APPLICATIONINSIGHTS_CONNECTION_STRING"
)

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "❌ Missing required env var: $var"
        exit 1
    fi
done

echo "✅ Environment variables OK"

# Check health endpoint
health_response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health)
if [ "$health_response" != "200" ]; then
    echo "❌ Health check failed: $health_response"
    exit 1
fi

echo "✅ Health check OK"

# Check database connectivity
# ... aggiungere check psql

echo "✅ All checks passed! Ready for production 🚀"
```

---

## Conclusioni

Seguendo questo piano di implementazione prioritizzato:

1. **Must Have** garantisce **stabilità minima** per produzione
2. **Should Have** migliora **resilienza e osservabilità**
3. **Could Have** ottimizza **costi e user experience**

**Tempo totale stimato:** 2-3 settimane per completamento Sprint 1+2

**Next Steps Immediati:**
1. Creare branch `feature/production-readiness`
2. Iniziare con Task 1 (Health Check)
3. Commit incrementali e testing continuo
4. Deploy su staging dopo Sprint 1
5. Load testing su staging
6. Deploy produzione dopo validazione completa

---

**Documento creato:** 2025-11-24  
**Versione:** 1.0  
**Priorità:** Alta

