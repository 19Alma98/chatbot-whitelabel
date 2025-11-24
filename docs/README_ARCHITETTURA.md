# 📚 Documentazione Architettura - Chatbot Whitelabel RAG

> **Documentazione completa per l'architettura di produzione dell'agente RAG**  
> Versione: 1.0 | Data: 2025-11-24

---

## 📋 Indice Documenti

### 🏛️ [1. Architettura di Produzione](./ARCHITETTURA_PRODUZIONE.md)
**Documento strategico completo**

Contenuto:
- ✅ Architettura generale del sistema
- ✅ Componenti core dell'agente (SimpleRAG, AdvancedRAG)
- ✅ Best practice per produzione (Scalabilità, Osservabilità, Sicurezza, Resilienza)
- ✅ Deployment su Azure Container Apps
- ✅ Costi stimati e ottimizzazione
- ✅ Checklist pre-produzione
- ✅ Monitoring e alerting
- ✅ Scaling roadmap

**Target:** CTO, Lead Developer, DevOps Engineer  
**Tempo lettura:** 30-40 minuti  
**Quando leggere:** Prima del deployment in produzione

---

### 🛠️ [2. Piano di Implementazione](./PIANO_IMPLEMENTAZIONE.md)
**Piano tattico con task pratici**

Contenuto:
- ✅ Prioritizzazione MoSCoW (Must/Should/Could Have)
- ✅ 11 task pratici con codice implementabile
- ✅ Timeline di implementazione (Sprint 1-3)
- ✅ Testing plan con Locust
- ✅ Monitoring alerts (Azure Monitor queries)
- ✅ Deployment checklist
- ✅ Script di automazione

**Target:** Developer, DevOps Engineer  
**Tempo implementazione:** 2-3 settimane  
**Quando usare:** Immediatamente per preparare produzione

---

### 📊 [3. Diagrammi Architettura](./DIAGRAMMI_ARCHITETTURA.md)
**Visualizzazioni con Mermaid**

Contenuto:
- ✅ Architettura generale (infrastruttura completa)
- ✅ Flussi RAG (Simple vs Advanced sequenceDiagram)
- ✅ Data flow (document ingestion pipeline)
- ✅ Deployment architecture (Azure services)
- ✅ Monitoring stack
- ✅ Conversation flow con persistenza
- ✅ Error handling & retry flow
- ✅ Security architecture
- ✅ Scaling strategy
- ✅ Cost optimization
- ✅ Disaster recovery plan

**Target:** Tutti (visuale)  
**Tempo review:** 15-20 minuti  
**Quando usare:** Per presentazioni, onboarding, troubleshooting

---

## 🚀 Quick Start

### Per iniziare subito:

1. **Se sei un CTO/Product Manager:**
   - Leggi: [Architettura di Produzione](./ARCHITETTURA_PRODUZIONE.md) (sezioni 1-5)
   - Focus: Costi, Scalabilità, ROI

2. **Se sei un Developer:**
   - Inizia da: [Piano di Implementazione](./PIANO_IMPLEMENTAZIONE.md) (Must Have tasks)
   - Implementa: Health checks, Retry logic, Rate limiting

3. **Se sei un DevOps Engineer:**
   - Studia: [Diagrammi Architettura](./DIAGRAMMI_ARCHITETTURA.md) (Deployment & Monitoring)
   - Configura: Azure Monitor alerts, CI/CD pipeline

4. **Per presentazioni a stakeholder:**
   - Usa: [Diagrammi Architettura](./DIAGRAMMI_ARCHITETTURA.md)
   - Mostra: Architettura generale, Costi, DR plan

---

## 🎯 Percorsi di Lettura Consigliati

### 📖 Percorso Completo (First Time)
```
1. Architettura Produzione (Sezione 1-3) [15min]
   ↓
2. Diagrammi - Architettura Generale [5min]
   ↓
3. Diagrammi - Flussi RAG [10min]
   ↓
4. Architettura Produzione (Sezione 4-8) [30min]
   ↓
5. Piano Implementazione - Must Have [20min]
   ↓
6. Piano Implementazione - Timeline [10min]
```
**Tempo totale:** ~90 minuti

---

### ⚡ Quick Reference (Urgente)
```
1. Diagrammi - Error Handling [3min]
   ↓
2. Piano Implementazione - Troubleshooting [5min]
   ↓
3. Architettura - Monitoring Dashboard [5min]
```
**Tempo totale:** ~15 minuti

---

### 🔒 Security Audit
```
1. Architettura - Sezione 4.3 Sicurezza [10min]
   ↓
2. Diagrammi - Security Architecture [5min]
   ↓
3. Piano Implementazione - Task 3 (Rate Limiting) [5min]
   ↓
4. Architettura - Checklist Sicurezza [5min]
```
**Tempo totale:** ~25 minuti

---

### 💰 Cost Optimization
```
1. Architettura - Sezione 9 Costi [10min]
   ↓
2. Piano Implementazione - Task 10 (Redis Cache) [10min]
   ↓
3. Diagrammi - Cost Optimization Strategy [5min]
   ↓
4. Architettura - Sezione 4.5 [10min]
```
**Tempo totale:** ~35 minuti

---

## 📊 Stato Implementazione Attuale

### ✅ Già Implementato (Production Ready)

| Feature | Status | Documento Riferimento |
|---------|--------|---------------------|
| FastAPI Backend | ✅ | Architettura §3.1 |
| RAG Engine (Simple + Advanced) | ✅ | Architettura §3.1, Diagrammi |
| PostgreSQL + pgvector | ✅ | Architettura §3.2 |
| Azure OpenAI Integration | ✅ | Architettura §2 |
| Conversation Service | ✅ | Architettura §3.3 |
| PDF Processing | ✅ | Architettura §3.4 |
| Azure Monitor + OpenTelemetry | ✅ | Architettura §4.2 |
| LangSmith Integration | ✅ | Architettura §4.2 |
| Managed Identity | ✅ | Architettura §4.3 |
| Database Migrations (Alembic) | ✅ | Architettura §4.6 |

---

### 🔶 Da Implementare (Must Have per Produzione)

| Feature | Priorità | Tempo | Documento Riferimento |
|---------|----------|-------|---------------------|
| Health Check Endpoint | 🔴 CRITICAL | 2h | Piano §1 |
| Retry Logic OpenAI | 🔴 CRITICAL | 4h | Piano §2 |
| Rate Limiting | 🔴 CRITICAL | 3h | Piano §3 |
| Structured Logging | 🔴 CRITICAL | 2h | Piano §4 |
| Environment Validation | 🔴 CRITICAL | 1h | Piano §5 |
| Graceful Shutdown | 🟡 HIGH | 2h | Piano §6 |
| Connection Pool Tuning | 🟡 HIGH | 1h | Piano §7 |
| Request Timeout | 🟡 HIGH | 1h | Piano §8 |
| Metrics Endpoint | 🟡 HIGH | 2h | Piano §9 |

**Total Must Have:** 18 ore (~3 giorni sviluppo)

---

### 🟢 Nice to Have (Ottimizzazioni)

| Feature | Priorità | ROI | Documento Riferimento |
|---------|----------|-----|---------------------|
| Redis Caching | 🟢 MEDIUM | 40-60% cost saving | Piano §10 |
| User Authentication | 🟢 MEDIUM | Security | Architettura §4.3 |
| A/B Testing Framework | 🟢 LOW | Product insights | Piano §11 |
| Multi-region Deployment | 🟢 LOW | HA | Architettura §8 |

---

## 🔧 Configurazione e Setup

### Variabili d'Ambiente Chiave

Vedi: [Architettura §5.2](./ARCHITETTURA_PRODUZIONE.md#52-environment-variables-produzione)

```bash
# Minimo richiesto per produzione
OPENAI_CHAT_HOST=azure
AZURE_OPENAI_ENDPOINT=https://<instance>.openai.azure.com
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4o-mini
POSTGRES_HOST=<db-server>.postgres.database.azure.com
APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=...
RUNNING_IN_PRODUCTION=true
```

---

### Comandi Utili

```bash
# Local development
python -m uvicorn fastapi_app:create_app --factory --reload

# Database migrations
alembic upgrade head

# Load testing
locust -f locustfile.py --host=http://localhost:8000

# Production deployment
azd up

# Health check
curl http://localhost:8000/health

# Metrics
curl http://localhost:8000/metrics
```

---

## 📈 Metriche di Successo

### Performance Targets

| Metrica | Target | Misurazione |
|---------|--------|-------------|
| P95 Latency | < 2000ms | Application Insights |
| Error Rate | < 0.5% | Application Insights |
| Uptime | > 99.5% | Azure Monitor |
| Token Usage | < 2000/request | LangSmith |
| Cache Hit Rate | > 40% | Redis metrics |

### Business Metrics

| Metrica | Target | Misurazione |
|---------|--------|-------------|
| Conversations/day | Baseline | Database query |
| Avg Messages/Conv | 5-10 | Database query |
| User Satisfaction | > 4/5 | Feedback API (da impl.) |
| Cost per Conversation | < $0.05 | Azure Cost Management |

Vedi: [Architettura §7](./ARCHITETTURA_PRODUZIONE.md#7-monitoring-dashboard-kpi-principali)

---

## 🆘 Troubleshooting Quick Reference

### Problema: High Latency

```
1. Check: Application Insights → Performance blade
2. Verify: OpenAI API status (status.openai.com)
3. Review: Database slow queries (Log Analytics)
4. Action: Scale up replicas se CPU > 80%

Riferimento: Diagrammi - Error Handling
```

### Problema: High Error Rate

```
1. Check: Application Insights → Failures blade
2. Review: Recent deployments (rollback se necessario)
3. Verify: Dependency health (OpenAI, PostgreSQL)
4. Action: Investigate logs con conversation_id

Riferimento: Architettura §4.4 - Resilienza
```

### Problema: High Costs

```
1. Check: Azure Cost Management → OpenAI spend
2. Review: Token usage per conversation (LangSmith)
3. Action: Implement Redis caching (Piano §10)
4. Action: Review token limit settings

Riferimento: Architettura §4.5 - Cost Optimization
```

### Problema: Database Connection Errors

```
1. Check: Connection pool metrics (Log Analytics)
2. Verify: PostgreSQL server health (Azure Portal)
3. Action: Tune pool_size (Piano §7)
4. Action: Review long-running queries

Riferimento: Architettura §4.6 - Database Management
```

---

## 🔗 Link Utili

### Documentazione Externa
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Azure OpenAI Service Docs](https://learn.microsoft.com/azure/ai-services/openai/)
- [pgvector GitHub](https://github.com/pgvector/pgvector)
- [Azure Container Apps Docs](https://learn.microsoft.com/azure/container-apps/)
- [OpenTelemetry Python](https://opentelemetry.io/docs/languages/python/)

### Best Practice Articles
- [Azure AI Architecture (Medium)](https://medium.com/@sridharcloud/azure-ai-architecture-what-they-dont-teach-in-tutorials-the-messy-reality-of-production-ai-92b54d8db8cf)
- [Production RAG Best Practices](https://docs.llamaindex.ai/en/stable/optimizing/production_rag/)

### Monitoring Tools
- [Azure Portal](https://portal.azure.com)
- [Application Insights](https://portal.azure.com/#blade/HubsExtension/BrowseResource/resourceType/microsoft.insights%2Fcomponents)
- [LangSmith Dashboard](https://smith.langchain.com/) (configurare LANGSMITH_PROJECT)

---

## 📝 Change Log

### Version 1.0 - 2025-11-24
- ✅ Documento Architettura Produzione completo
- ✅ Piano Implementazione con 11 task pratici
- ✅ 11 diagrammi Mermaid (architettura, flussi, deployment)
- ✅ README navigazione e quick start
- ✅ Best practice da articolo Azure AI
- ✅ Checklist pre-produzione
- ✅ Troubleshooting guide

### Prossimi Aggiornamenti Pianificati
- [ ] v1.1: Aggiungere esempi Terraform/Bicep per IaC
- [ ] v1.2: Guida dettagliata setup CI/CD
- [ ] v1.3: Disaster Recovery runbook completo
- [ ] v1.4: Performance tuning avanzato

---

## 👥 Contributori e Contatti

### Team Ownership

| Area | Owner | Contatto |
|------|-------|----------|
| Architecture | Tech Lead | - |
| Development | Dev Team | - |
| DevOps | DevOps Lead | - |
| Security | Security Team | - |

### Come Contribuire

1. Leggi la documentazione esistente
2. Crea un branch: `git checkout -b docs/update-architecture`
3. Aggiorna la documentazione
4. Crea una PR con descrizione dettagliata
5. Request review dal Tech Lead

---

## 📊 Metriche Documentazione

| Metrica | Valore |
|---------|--------|
| **Documenti Totali** | 4 |
| **Pagine Totali** | ~80 |
| **Diagrammi** | 11 |
| **Code Examples** | 25+ |
| **Checklist Items** | 30+ |
| **Tempo Lettura Completo** | ~2 ore |

---

## 🎓 Risorse per Onboarding

### New Developer (Prima Settimana)

**Giorno 1-2: Comprensione Sistema**
- [ ] Leggi [Architettura §1-3](./ARCHITETTURA_PRODUZIONE.md)
- [ ] Studia [Diagrammi - Architettura Generale](./DIAGRAMMI_ARCHITETTURA.md)
- [ ] Setup ambiente locale (README.md principale)

**Giorno 3-4: Deep Dive Tecnico**
- [ ] Leggi [Architettura §4-6](./ARCHITETTURA_PRODUZIONE.md)
- [ ] Studia [Diagrammi - Flussi RAG](./DIAGRAMMI_ARCHITETTURA.md)
- [ ] Review codice: `rag_simple.py`, `rag_advanced.py`

**Giorno 5: Hands-on**
- [ ] Implementa una feature dal [Piano](./PIANO_IMPLEMENTAZIONE.md)
- [ ] Esegui tests locali
- [ ] Code review con senior developer

---

### New DevOps Engineer

**Giorno 1: Infrastruttura**
- [ ] [Diagrammi - Deployment Architecture](./DIAGRAMMI_ARCHITETTURA.md)
- [ ] [Architettura §5 - Deployment](./ARCHITETTURA_PRODUZIONE.md)
- [ ] Review bicep/terraform files (se disponibili)

**Giorno 2: Monitoring**
- [ ] [Architettura §4.2 - Observability](./ARCHITETTURA_PRODUZIONE.md)
- [ ] [Diagrammi - Monitoring Stack](./DIAGRAMMI_ARCHITETTURA.md)
- [ ] Setup Azure Monitor dashboards

**Giorno 3-4: Automation**
- [ ] [Piano - CI/CD](./PIANO_IMPLEMENTAZIONE.md)
- [ ] Review GitHub Actions workflows
- [ ] Setup staging environment

**Giorno 5: DR Planning**
- [ ] [Diagrammi - Disaster Recovery](./DIAGRAMMI_ARCHITETTURA.md)
- [ ] Test backup restore
- [ ] Document runbooks

---

## 🚨 Alerts & Incidents

### Severità Incidents

| Severity | Response Time | Esempi |
|----------|--------------|---------|
| **P0 - Critical** | 15 min | Sistema down, data loss |
| **P1 - High** | 1 hour | Error rate > 5%, latency > 5s |
| **P2 - Medium** | 4 hours | Degraded performance |
| **P3 - Low** | 1 day | Minor bugs, feature requests |

### Escalation Path

```
P0/P1 Incident
    ↓
On-call Developer (15min response)
    ↓ (se non risolvibile in 30min)
Tech Lead
    ↓ (se non risolvibile in 1h)
CTO + DevOps Lead
```

---

## ✅ Pre-Production Checklist

Copia questa checklist prima del deployment:

### Security
- [ ] Authentication implementata
- [ ] Rate limiting attivo
- [ ] Secrets in Key Vault
- [ ] Content filtering testato
- [ ] Security scan completato

### Performance
- [ ] Load testing eseguito (target: 1000 req/min)
- [ ] P95 latency < 2s
- [ ] Error rate < 0.5%
- [ ] Cache hit rate > 40% (se Redis attivo)

### Monitoring
- [ ] Application Insights configurato
- [ ] Dashboards creati
- [ ] Alerts configurati (5 alert rules minimo)
- [ ] On-call rotation definita
- [ ] Runbook documentati

### Database
- [ ] Migrations testate su staging
- [ ] Indexes ottimizzati
- [ ] Backup policy attiva
- [ ] Restore testato (ultimo 7 giorni)

### Documentation
- [ ] README aggiornato
- [ ] API documentation generata
- [ ] Architecture docs reviewed
- [ ] Onboarding guide completa

### Testing
- [ ] Unit tests pass (coverage > 80%)
- [ ] Integration tests pass
- [ ] Load tests pass
- [ ] Smoke tests su staging pass

---

## 🎯 Next Steps

### Immediate (Questa Settimana)
1. ✅ Review completo documentazione con team
2. ⬜ Prioritizzare task dal [Piano Implementazione](./PIANO_IMPLEMENTAZIONE.md)
3. ⬜ Creare sprint planning per Must Have tasks
4. ⬜ Setup staging environment

### Short Term (Prossimo Mese)
1. ⬜ Implementare tutti i Must Have (18h sviluppo)
2. ⬜ Load testing su staging
3. ⬜ Security audit
4. ⬜ Deploy produzione (soft launch)

### Medium Term (3-6 Mesi)
1. ⬜ Implementare Should Have features
2. ⬜ Ottimizzazioni performance e costi
3. ⬜ A/B testing framework
4. ⬜ Scale a multiple regions

### Long Term (6-12 Mesi)
1. ⬜ Enterprise features (multi-tenancy)
2. ⬜ Advanced AI features (fine-tuning, custom models)
3. ⬜ White-label customization per cliente
4. ⬜ 99.99% SLA commitment

---

## 📚 Additional Resources

### Internal Documentation
- [Main README](../README.md)
- [RAG Flow Details](./rag_flow.md) (se esistente)
- [API Documentation](./example_chat_params.md)

### Training Materials
- [ ] Video walkthrough (da creare)
- [ ] Architecture presentation slides (da creare)
- [ ] Developer quickstart (da creare)

---

## 💬 Feedback

Questa documentazione è in continua evoluzione. Per feedback o suggerimenti:

1. **Bug nella documentazione:** Apri un issue
2. **Suggerimenti miglioramenti:** Crea una PR
3. **Domande urgenti:** Contatta il Tech Lead
4. **Discussioni architetturali:** Programma un design review

---

**Last Updated:** 2025-11-24  
**Next Review:** 2025-12-24 (monthly review)  
**Document Owner:** Tech Lead / Architecture Team

---

<div align="center">

### 🚀 Ready to Deploy to Production?

**Start here:** [Piano di Implementazione - Must Have Tasks](./PIANO_IMPLEMENTAZIONE.md#🔴-must-have-blocker-per-produzione)

</div>

