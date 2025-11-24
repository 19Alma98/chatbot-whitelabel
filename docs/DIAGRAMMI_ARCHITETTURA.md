# Diagrammi Architettura - Agente RAG Chatbot

## Indice
1. [Architettura Generale](#architettura-generale)
2. [Flusso RAG Semplice](#flusso-rag-semplice)
3. [Flusso RAG Avanzato](#flusso-rag-avanzato)
4. [Data Flow](#data-flow)
5. [Deployment Architecture](#deployment-architecture)
6. [Monitoring Stack](#monitoring-stack)

---

## Architettura Generale

```mermaid
graph TB
    subgraph "Client Layer"
        A[Frontend React]
        B[Mobile App]
        C[API Clients]
    end

    subgraph "API Gateway"
        D[Azure Container Apps Ingress]
        D1[Load Balancer]
        D2[TLS Termination]
    end

    subgraph "Application Layer - Azure Container Apps"
        E1[FastAPI Instance 1]
        E2[FastAPI Instance 2]
        E3[FastAPI Instance N]
        
        E1 --> F[RAG Engine]
        E2 --> F
        E3 --> F
        
        F --> F1[Simple RAG]
        F --> F2[Advanced RAG]
    end

    subgraph "Data Layer"
        G[(PostgreSQL<br/>+ pgvector)]
        H[Azure AI Search]
        I[(Redis Cache<br/>Optional)]
    end

    subgraph "AI Services"
        J[Azure OpenAI]
        J1[GPT-4o-mini<br/>Chat]
        J2[text-embedding-ada-002<br/>Embeddings]
        J --> J1
        J --> J2
    end

    subgraph "Observability"
        K[Azure Monitor]
        K1[Application Insights]
        K2[Log Analytics]
        L[LangSmith]
        K --> K1
        K --> K2
    end

    subgraph "Security"
        M[Azure AD]
        N[Managed Identity]
        O[Key Vault]
    end

    A --> D
    B --> D
    C --> D
    D --> D1
    D1 --> D2
    D2 --> E1
    D2 --> E2
    D2 --> E3

    F1 -.Query.-> G
    F1 -.Query.-> H
    F2 -.Query.-> G
    F2 -.Query.-> H
    
    F1 -.Cache.-> I
    F2 -.Cache.-> I

    F1 --> J
    F2 --> J

    E1 -.Logs/Traces.-> K
    E2 -.Logs/Traces.-> K
    E3 -.Logs/Traces.-> K
    F -.LLM Traces.-> L

    N -.Authenticate.-> G
    N -.Authenticate.-> J
    N -.Authenticate.-> H

    style F fill:#e1f5ff
    style J fill:#ffe1e1
    style G fill:#e1ffe1
    style K fill:#fff4e1
```

---

## Flusso RAG Semplice (SimpleRAGChat)

```mermaid
sequenceDiagram
    actor User
    participant API as FastAPI
    participant RAG as Simple RAG
    participant VDB as Vector DB
    participant Embed as Embeddings API
    participant LLM as Chat LLM
    participant DB as PostgreSQL

    User->>API: POST /chat {"message": "What is..."}
    
    API->>DB: Load conversation history
    DB-->>API: Previous messages
    
    API->>RAG: Process chat request
    
    RAG->>Embed: Create embedding for query
    Embed-->>RAG: Query vector
    
    RAG->>VDB: Hybrid search<br/>(vector + full-text)
    VDB-->>RAG: Top K documents
    
    RAG->>RAG: Build context from documents
    RAG->>RAG: Assemble prompt with context
    
    RAG->>LLM: Generate response<br/>(with retrieved context)
    LLM-->>RAG: Response text
    
    RAG-->>API: RetrievalResponse
    
    API->>DB: Save user message & response
    
    API-->>User: {"message": "...", "context": [...]}

    Note over RAG,LLM: Latency: 800-1500ms
```

### Caratteristiche SimpleRAG
- **Latenza:** 800-1500ms
- **Costo:** ~$0.002-0.005 per richiesta
- **Use Case:** FAQ, ricerca documenti, Q&A dirette
- **Token Usage:** 500-1500 tokens/richiesta

---

## Flusso RAG Avanzato (AdvancedRAGChat)

```mermaid
sequenceDiagram
    actor User
    participant API as FastAPI
    participant RAG as Advanced RAG
    participant QR as Query Rewriter
    participant VDB as Vector DB
    participant LLM as Chat LLM
    participant DB as PostgreSQL

    User->>API: POST /chat {"message": "Show climbing ropes under $50"}
    
    API->>DB: Load conversation history
    DB-->>API: Previous messages
    
    API->>RAG: Process chat request
    
    RAG->>QR: Rewrite query + extract filters
    Note over RAG,QR: Function calling per<br/>estrarre filtri SQL
    
    QR->>LLM: Generate search parameters<br/>(with function schema)
    LLM-->>QR: {"search_query": "climbing ropes",<br/>"filters": "price < 50"}
    
    RAG->>VDB: Hybrid search with filters
    VDB-->>RAG: Filtered top K documents
    
    RAG->>RAG: Multi-step reasoning<br/>(thoughts generation)
    
    RAG->>LLM: Generate final response<br/>(with context + filters)
    LLM-->>RAG: Response text + thoughts
    
    RAG-->>API: RetrievalResponse<br/>(+ thoughts + filters)
    
    API->>DB: Save with metadata<br/>(thoughts, filters, docs)
    
    API-->>User: {"message": "...", "thoughts": [...]}

    Note over RAG,LLM: Latency: 1500-3000ms
```

### Caratteristiche AdvancedRAG
- **Latenza:** 1500-3000ms (doppia chiamata LLM)
- **Costo:** ~$0.005-0.012 per richiesta
- **Use Case:** Analisi complesse, filtri dinamici, reasoning multi-step
- **Token Usage:** 1000-3000 tokens/richiesta
- **Features:** Query rewriting, function calling, thought tracking

---

## Data Flow - Document Ingestion

```mermaid
graph LR
    A[PDF Upload] -->|POST /upload-pdf| B[PDF Processor]
    
    B --> C[Extract Text]
    C --> D[Chunking Strategy]
    
    D --> D1[LangChain<br/>RecursiveCharacterTextSplitter]
    D1 --> D2[Chunk Size: 1000<br/>Overlap: 200]
    
    D2 --> E[Batch Processing]
    
    E --> F[Generate Embeddings]
    F -->|Azure OpenAI| F1[Embedding API]
    F1 -->|Vector 1536 dim| F2[Embedding Results]
    
    F2 --> G[Store in DB]
    
    G --> G1[(PostgreSQL)]
    G1 --> G2[Documents Table]
    G1 --> G3[pgvector Index]
    
    G --> G4[Azure AI Search]
    G4 --> G5[Search Index]
    
    style B fill:#e1f5ff
    style F fill:#ffe1e1
    style G1 fill:#e1ffe1
    style G4 fill:#fff4e1
```

### Pipeline Steps
1. **Upload:** Receive PDF via API
2. **Extraction:** pypdf library
3. **Chunking:** Recursive splitter (1000 chars, 200 overlap)
4. **Embedding:** Batch API calls (max 100 chunks/batch)
5. **Storage:** PostgreSQL + pgvector OR Azure AI Search
6. **Indexing:** Automatic HNSW index creation

**Throughput:** ~50 pages/minute

---

## Deployment Architecture (Azure)

```mermaid
graph TB
    subgraph "Azure Region - Primary"
        subgraph "Container Apps Environment"
            A[Load Balancer]
            A --> B1[App Instance 1]
            A --> B2[App Instance 2]
            A --> B3[App Instance N]
            
            B1 -.-> C[Managed Identity]
            B2 -.-> C
            B3 -.-> C
        end
        
        subgraph "Database Services"
            D[(PostgreSQL<br/>Flexible Server)]
            D1[Read Replicas]
            D -.Replication.-> D1
        end
        
        subgraph "AI Services"
            E[Azure OpenAI]
            E1[GPT-4o-mini]
            E2[Embeddings]
            E --> E1
            E --> E2
        end
        
        subgraph "Search Services"
            F[Azure AI Search]
            F1[Search Index]
            F --> F1
        end
        
        subgraph "Cache Layer"
            G[(Redis Cache)]
        end
        
        B1 --> D
        B2 --> D
        B3 --> D
        
        B1 --> E
        B2 --> E
        B3 --> E
        
        B1 -.Optional.-> F
        B2 -.Optional.-> F
        B3 -.Optional.-> F
        
        B1 -.Cache.-> G
        B2 -.Cache.-> G
        B3 -.Cache.-> G
    end
    
    subgraph "Monitoring & Security"
        H[Application Insights]
        I[Log Analytics]
        J[Key Vault]
        K[Azure AD]
        
        B1 -.Telemetry.-> H
        B2 -.Telemetry.-> H
        B3 -.Telemetry.-> H
        
        H --> I
        
        C -.Secrets.-> J
        C -.Auth.-> K
    end
    
    subgraph "CI/CD"
        L[GitHub Actions]
        M[Container Registry]
        
        L -->|Build & Push| M
        M -->|Deploy| B1
        M -->|Deploy| B2
        M -->|Deploy| B3
    end
    
    subgraph "Backup & DR"
        N[Azure Backup]
        O[Geo-Redundant Storage]
        
        D -.Backup.-> N
        N --> O
    end

    style B1 fill:#e1f5ff
    style B2 fill:#e1f5ff
    style B3 fill:#e1f5ff
    style E fill:#ffe1e1
    style D fill:#e1ffe1
    style H fill:#fff4e1
```

### Infrastructure Components

| Component | SKU | Auto-Scale | Availability |
|-----------|-----|------------|--------------|
| Container Apps | 1vCPU, 2GB | 2-10 replicas | 99.9% |
| PostgreSQL | Standard_B2s | Manual | 99.99% |
| Azure OpenAI | Standard | Auto | 99.9% |
| Redis Cache | Basic C0 | No | 99.9% |
| AI Search | Standard S1 | No | 99.9% |

---

## Monitoring Stack

```mermaid
graph TB
    subgraph "Application"
        A[FastAPI App]
        A1[OpenTelemetry SDK]
        A2[Structured Logging]
        A --> A1
        A --> A2
    end
    
    subgraph "Instrumentation"
        B[OpenAI Instrumentor]
        C[SQLAlchemy Instrumentor]
        D[FastAPI Instrumentor]
        E[AIOHTTP Instrumentor]
        
        A1 --> B
        A1 --> C
        A1 --> D
        A1 --> E
    end
    
    subgraph "Collection"
        F[Azure Monitor Exporter]
        G[LangSmith SDK]
        
        B --> F
        C --> F
        D --> F
        E --> F
        
        B -.LLM Traces.-> G
    end
    
    subgraph "Storage & Analysis"
        H[Application Insights]
        I[Log Analytics Workspace]
        J[LangSmith Platform]
        
        F --> H
        H --> I
        G --> J
    end
    
    subgraph "Visualization"
        K[Azure Dashboards]
        L[Workbooks]
        M[LangSmith UI]
        N[Grafana<br/>Optional]
        
        I --> K
        I --> L
        J --> M
        I -.Export.-> N
    end
    
    subgraph "Alerting"
        O[Alert Rules]
        P[Action Groups]
        Q[Notifications]
        
        I --> O
        O --> P
        P --> Q
        
        Q --> Q1[Email]
        Q --> Q2[SMS]
        Q --> Q3[Slack/Teams]
    end

    style A fill:#e1f5ff
    style F fill:#ffe1e1
    style I fill:#e1ffe1
    style O fill:#fff4e1
```

### Metriche Monitorate

#### Application Metrics
- Request rate (req/s)
- Response time (P50, P95, P99)
- Error rate (%)
- Active connections

#### AI Metrics
- OpenAI token usage (prompt/completion)
- Embedding API latency
- LLM response latency
- Function calling success rate
- Cache hit rate (se Redis abilitato)

#### Database Metrics
- Query execution time
- Connection pool utilization
- Active connections
- Vector search performance
- Full-text search latency

#### Business Metrics
- Conversations created
- Messages per conversation
- Retrieval accuracy (context relevance)
- User satisfaction (feedback)
- Documents indexed

---

## Conversation Flow con Persistenza

```mermaid
sequenceDiagram
    actor User
    participant API as FastAPI
    participant Conv as Conversation Service
    participant DB as PostgreSQL
    participant RAG as RAG Engine
    participant Cache as Redis<br/>(Optional)

    Note over User,DB: Nuova Conversazione
    
    User->>API: POST /chat (no conversation_id)
    API->>Conv: Generate conversation_id
    Conv-->>API: conv_123abc
    
    API->>Conv: Save user message
    Conv->>DB: INSERT INTO conversation_messages
    
    API->>RAG: Process request (no history)
    RAG-->>API: Response
    
    API->>Conv: Save assistant message + metadata
    Conv->>DB: INSERT INTO conversation_messages<br/>(+ chat_params, thoughts, docs)
    
    API-->>User: Response + conversation_id
    
    Note over User,DB: Messaggio Successivo
    
    User->>API: POST /chat (conversation_id=conv_123abc)
    
    API->>Cache: Check cached history
    alt Cache Miss
        Cache-->>API: null
        API->>Conv: Load conversation history
        Conv->>DB: SELECT * WHERE conversation_id<br/>ORDER BY created_at
        DB-->>Conv: All messages
        Conv-->>API: Message list
        API->>Cache: Cache history (TTL 5min)
    else Cache Hit
        Cache-->>API: Cached history
    end
    
    API->>RAG: Process request (with history)
    Note over RAG: Context window management<br/>Trim old messages if needed
    
    RAG-->>API: Response
    
    API->>Conv: Save user + assistant messages
    Conv->>DB: INSERT messages
    
    API->>Cache: Invalidate cached history
    
    API-->>User: Response

    Note over User,DB: Gestione Conversazione
    
    User->>API: GET /conversations/{id}
    API->>Conv: Get conversation
    Conv->>DB: SELECT messages
    DB-->>Conv: Messages + metadata
    Conv-->>API: ConversationHistory
    API-->>User: Full conversation + debug data

    User->>API: DELETE /conversations/{id}
    API->>Conv: Delete conversation
    Conv->>DB: DELETE FROM conversation_messages
    DB-->>Conv: Deleted count
    Conv-->>API: Success
    API-->>User: Confirmation
```

### Database Schema

```sql
-- Conversation Messages Table
CREATE TABLE conversation_messages (
    id SERIAL PRIMARY KEY,
    conversation_id VARCHAR(255) NOT NULL,
    message_role VARCHAR(50) NOT NULL,  -- 'user' | 'assistant' | 'system'
    message_content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Debug & Tracing Data (JSON)
    chat_params JSONB,              -- RAG parameters used
    contextual_messages JSONB,      -- Full context sent to LLM
    document_ids TEXT[],            -- Retrieved document IDs
    thoughts JSONB,                 -- Reasoning steps (AdvancedRAG)
    
    -- Indexes
    INDEX idx_conversation_id (conversation_id),
    INDEX idx_created_at (created_at DESC),
    INDEX idx_conversation_created (conversation_id, created_at DESC)
);

-- Optional: User tracking
ALTER TABLE conversation_messages 
    ADD COLUMN user_id VARCHAR(255);

CREATE INDEX idx_user_conversations 
    ON conversation_messages(user_id, created_at DESC);
```

---

## Error Handling & Retry Flow

```mermaid
graph TB
    A[Incoming Request] --> B{Request Validation}
    
    B -->|Valid| C[Process Request]
    B -->|Invalid| Z1[400 Bad Request]
    
    C --> D{Rate Limit Check}
    D -->|Exceeded| Z2[429 Too Many Requests]
    D -->|OK| E[Execute RAG Flow]
    
    E --> F{OpenAI API Call}
    
    F -->|Success| G[Return Response]
    F -->|Rate Limit Error| H{Retry Count < 3?}
    F -->|Timeout| H
    F -->|Connection Error| H
    
    H -->|Yes| I[Exponential Backoff]
    I -->|Wait 2^n seconds| F
    H -->|No| J{Fallback Available?}
    
    J -->|Yes| K[Use Simple RAG]
    K --> F
    J -->|No| Z3[503 Service Unavailable]
    
    F -->|Content Filter| Z4[400 Content Filtered]
    F -->|Other Error| Z5[500 Internal Server Error]
    
    G --> L[Save to DB]
    L -->|Success| M[Return to Client]
    L -->|DB Error| N[Log Error + Return Response]
    N --> M
    
    Z1 --> O[Log & Return Error]
    Z2 --> O
    Z3 --> O
    Z4 --> O
    Z5 --> O
    
    style G fill:#e1ffe1
    style Z1 fill:#ffe1e1
    style Z2 fill:#ffe1e1
    style Z3 fill:#ffe1e1
    style Z4 fill:#ffe1e1
    style Z5 fill:#ffe1e1
```

### Error Categories

| Error Type | HTTP Code | Retry? | User Message |
|------------|-----------|--------|--------------|
| Validation Error | 400 | No | "Invalid request parameters" |
| Rate Limit (App) | 429 | Yes | "Too many requests, try again later" |
| Content Filter | 400 | No | "Content flagged by safety filter" |
| OpenAI Rate Limit | 429 | Yes (auto) | Processing (transparent retry) |
| OpenAI Timeout | 504 | Yes (auto) | Processing (transparent retry) |
| Database Error | 500 | No | "Service temporarily unavailable" |
| Generic Error | 500 | No | "An error occurred, please try again" |

---

## Security Architecture

```mermaid
graph TB
    subgraph "External Access"
        A[Internet]
        B[API Gateway]
        A -->|HTTPS only| B
    end
    
    subgraph "Authentication & Authorization"
        C[Azure AD]
        D[JWT Validation]
        E[Rate Limiter]
        
        B --> D
        D --> C
        D --> E
    end
    
    subgraph "Application Layer"
        F[FastAPI App]
        G[Request Context]
        
        E --> F
        F --> G
    end
    
    subgraph "Managed Identity"
        H[User Assigned<br/>Managed Identity]
        
        F --> H
    end
    
    subgraph "Data Access Layer"
        I[(PostgreSQL)]
        J[Azure OpenAI]
        K[Azure AI Search]
        
        H -.Passwordless Auth.-> I
        H -.Azure AD Auth.-> J
        H -.Azure AD Auth.-> K
    end
    
    subgraph "Secrets Management"
        L[Azure Key Vault]
        
        H -.Access.-> L
        L -.Retrieve.-> F
    end
    
    subgraph "Data Protection"
        M[Encryption at Rest]
        N[TLS in Transit]
        O[Row-Level Security<br/>Optional]
        
        I --> M
        I --> O
        B -.-> N
    end
    
    subgraph "Monitoring & Audit"
        P[Azure Monitor]
        Q[Audit Logs]
        
        F -.Telemetry.-> P
        I -.Audit Trail.-> Q
        L -.Access Logs.-> Q
    end

    style H fill:#e1f5ff
    style L fill:#ffe1e1
    style M fill:#e1ffe1
    style P fill:#fff4e1
```

### Security Checklist

- [x] TLS 1.2+ per tutte le connessioni
- [x] Managed Identity per servizi Azure (no passwords)
- [ ] JWT authentication per API (da implementare)
- [ ] Row-Level Security su PostgreSQL (da implementare)
- [x] Content filtering Azure OpenAI
- [ ] Rate limiting per utente (da implementare)
- [x] Audit logging
- [x] Encryption at rest (Azure default)
- [ ] Input validation rigorosa (da migliorare)
- [ ] CORS policy restrittiva (da configurare)

---

## Scaling Strategy

```mermaid
graph LR
    A[Load Increase] --> B{CPU > 70%<br/>or<br/>Requests > 50/replica}
    
    B -->|Yes| C[Scale Out]
    C --> D[Add Container Instance]
    D --> E[Health Check]
    
    E -->|Pass| F[Add to Load Balancer]
    E -->|Fail| G[Terminate & Retry]
    G --> D
    
    F --> H[Distribute Traffic]
    
    B -->|No| I{CPU < 30%<br/>and<br/>Requests < 20/replica}
    
    I -->|Yes| J[Scale In]
    J --> K{Replicas > Min?}
    
    K -->|Yes| L[Graceful Shutdown]
    L --> M[Drain Connections]
    M --> N[Remove Instance]
    
    K -->|No| O[Keep Running]
    
    I -->|No| O
    
    H --> P{Monitor Performance}
    P --> A

    style F fill:#e1ffe1
    style L fill:#fff4e1
```

### Scaling Configuration

```yaml
scale:
  minReplicas: 2
  maxReplicas: 10
  rules:
    - name: http-scaling
      http:
        metadata:
          concurrentRequests: "50"
    
    - name: cpu-scaling
      custom:
        type: cpu
        metadata:
          type: Utilization
          value: "70"
    
    - name: memory-scaling
      custom:
        type: memory
        metadata:
          type: Utilization
          value: "80"
```

### Scaling Behavior

| Metric | Scale Out Threshold | Scale In Threshold | Cooldown |
|--------|-------------------|-------------------|----------|
| CPU | > 70% per 5min | < 30% per 10min | 5min |
| Memory | > 80% per 5min | < 40% per 10min | 5min |
| HTTP Requests | > 50 concurrent | < 20 concurrent | 3min |

**Scaling Time:**
- Scale out: 30-60 secondi (container start + health check)
- Scale in: 90-120 secondi (graceful shutdown + drain)

---

## Cost Optimization Strategy

```mermaid
graph TB
    A[Cost Optimization] --> B[Caching Strategy]
    A --> C[Model Selection]
    A --> D[Resource Rightsizing]
    A --> E[Smart Retry]
    
    B --> B1[Redis Embedding Cache]
    B1 --> B2[40-60% API Cost Reduction]
    
    C --> C1{Query Complexity}
    C1 -->|Low| C2[gpt-3.5-turbo<br/>$0.001/1K tokens]
    C1 -->|Medium| C3[gpt-4o-mini<br/>$0.003/1K tokens]
    C1 -->|High| C4[gpt-4o<br/>$0.03/1K tokens]
    
    D --> D1[Auto-scaling]
    D1 --> D2[Pay only for active replicas]
    
    D --> D3[Connection Pooling]
    D3 --> D4[Optimize DB costs]
    
    E --> E1[Circuit Breaker]
    E1 --> E2[Avoid wasted API calls]
    
    E --> E3[Exponential Backoff]
    E3 --> E4[Smart retry timing]
    
    B2 --> F[Total Savings]
    D2 --> F
    D4 --> F
    E2 --> F
    E4 --> F
    
    F --> G[30-50% Cost Reduction]

    style B1 fill:#e1ffe1
    style D1 fill:#e1f5ff
    style F fill:#fff4e1
```

### Cost Breakdown (mensile, 10K conversazioni)

| Categoria | Senza Ottimizzazioni | Con Ottimizzazioni | Risparmio |
|-----------|---------------------|-------------------|-----------|
| Azure OpenAI | $250 | $120 (-52%) | $130 |
| Container Apps | $300 | $180 (-40%) | $120 |
| PostgreSQL | $120 | $120 (0%) | $0 |
| Redis Cache | $0 | $15 | -$15 |
| Monitoring | $100 | $80 (-20%) | $20 |
| **TOTALE** | **$770** | **$515** | **$255 (33%)** |

**Ottimizzazioni chiave:**
1. Redis caching → -52% costi OpenAI
2. Auto-scaling → -40% costi Container Apps
3. Query optimization → Migliori performance

---

## Disaster Recovery Plan

```mermaid
graph TB
    A[Production System] -->|Continuous| B[Automated Backups]
    
    B --> B1[Database Backups<br/>Daily + Point-in-Time]
    B --> B2[Configuration Backups<br/>Git + Azure DevOps]
    B --> B3[Monitoring Data<br/>Log Analytics retention]
    
    A -->|Disaster Event| C{Failure Type}
    
    C -->|Database Corruption| D[DB Restore]
    D --> D1[Select restore point]
    D1 --> D2[Restore from backup<br/>5-15 min]
    D2 --> D3[Verify data integrity]
    D3 --> D4[Switch traffic]
    
    C -->|Application Failure| E[Rollback Deployment]
    E --> E1[Identify last good version]
    E1 --> E2[Deploy previous image<br/>2-5 min]
    E2 --> E3[Run smoke tests]
    E3 --> D4
    
    C -->|Infrastructure Failure| F[Failover to DR Region]
    F --> F1[Update DNS<br/>Manual]
    F1 --> F2[Spin up in DR region<br/>15-30 min]
    F2 --> F3[Restore data]
    F3 --> D4
    
    D4 --> G[Monitor System]
    G --> H{System Healthy?}
    
    H -->|Yes| I[Post-Mortem]
    I --> J[Document & Improve]
    
    H -->|No| K[Escalate]
    K --> L[Senior Engineer]
    L --> M[Root Cause Analysis]
    M --> D4

    style D4 fill:#e1ffe1
    style H fill:#fff4e1
    style K fill:#ffe1e1
```

### RTO/RPO Targets

| Scenario | RTO (Recovery Time) | RPO (Data Loss) | Impact |
|----------|-------------------|----------------|--------|
| Database failure | 15 min | 5 min | Medium |
| App deployment issue | 5 min | 0 (rollback) | Low |
| Region outage | 1-2 hours | 15 min | High |
| Data corruption | 30 min | 1 hour | Medium |

**Backup Strategy:**
- Database: Continuous (point-in-time restore)
- Configuration: Git + IaC (Infrastructure as Code)
- Retention: 30 days production, 7 giorni staging

---

## Performance Optimization Roadmap

```mermaid
gantt
    title Performance Optimization Timeline
    dateFormat  YYYY-MM-DD
    section Phase 1
    Health Checks & Monitoring    :done, p1, 2025-11-25, 2d
    Retry Logic                   :done, p2, 2025-11-27, 2d
    Rate Limiting                 :active, p3, 2025-11-29, 2d
    
    section Phase 2
    Connection Pool Tuning        :p4, 2025-12-01, 1d
    Graceful Shutdown             :p5, 2025-12-02, 2d
    Request Timeout               :p6, 2025-12-04, 1d
    Structured Logging            :p7, 2025-12-05, 2d
    
    section Phase 3
    Redis Caching                 :p8, 2025-12-07, 5d
    Query Optimization            :p9, 2025-12-12, 3d
    Database Indexing             :p10, 2025-12-15, 2d
    
    section Phase 4
    Load Testing                  :p11, 2025-12-17, 3d
    Performance Tuning            :p12, 2025-12-20, 3d
    Production Deployment         :milestone, p13, 2025-12-23, 0d
```

---

## Conclusioni

Questi diagrammi forniscono una visione completa dell'architettura del sistema RAG:

✅ **Architettura Generale:** Overview completo dei componenti  
✅ **Flussi RAG:** Dettagli implementativi Simple vs Advanced  
✅ **Data Flow:** Pipeline di ingestion documenti  
✅ **Deployment:** Infrastruttura Azure completa  
✅ **Monitoring:** Stack di osservabilità  
✅ **Security:** Strategie di sicurezza  
✅ **Scaling:** Auto-scaling e performance  
✅ **DR:** Disaster recovery planning  

**Usa questi diagrammi per:**
- Onboarding nuovi sviluppatori
- Documentazione tecnica
- Presentazioni a stakeholder
- Planning architetturale
- Troubleshooting e debugging

---

**Documento creato:** 2025-11-24  
**Versione:** 1.0  
**Formato:** Mermaid Diagrams (compatibile GitHub/GitLab)

