Here we got an example of what is created in `rag_flow.get_params()`

```
+ top=3
+ temperature=0.3
+ retrieval_mode=<RetrievalMode.HYBRID: 'hybrid'>
+ use_advanced_flow=True
+ prompt_template="Assistant helps customers with questions about products.\nRespond as if you are an assistant helping a customer. Do NOT respond with tables.\nIf there isn't enough information below, say you don't know.\nDo not generate answers that don't use the sources below.\nEach product has a file name in brackets followed by colon and the details about it.\nAlways include the name of the file as information source, use square brackets to reference the source, for example [file_name]."
+ seed=None
+ response_token_limit=1024
+ enable_text_search=True
+ enable_vector_search=True
original_user_query='e timesheet?'
+ past_messages=[{'content': 'ciao, chi sei?', 'role': 'user'}, {'role': 'assistant', 'content': 'Ciao! Sono Orbyta, un assistente virtuale. Posso aiutarti con informazioni, risposte a domande e supporto su vari argomenti. Come posso aiutarti oggi?'}, {'content': 'trasferte?', 'role': 'user'}, {'role': 'assistant', 'content': "Ecco alcune informazioni sulle trasferte aziendali presso ORBYTA Tech e Strategy:\n\n- Le trasferte devono essere concordate e approvate dal proprio responsabile.\n- Gli acquisti relativi alla trasferta (trasporti e alloggio) devono essere effettuati direttamente dall'Orbyter interessato/a, seguendo le linee guida indicate nel documento.\n- Per l'acquisto dei biglietti dei mezzi di trasporto, è consigliabile scegliere il mezzo più veloce ed economico. Per il pernottamento, è disponibile un budget massimo di 80 € a notte.\n- Per ottenere il rimborso dei costi di viaggio e pernottamento, è necessario presentare una fattura intestata alla propria società di riferimento o una ricevuta di pagamento.\n- Viene riconosciuta un'indennità di trasferta di 30€ al giorno per trasferte superiori alle 12 ore, inclusi eventuali pasti non coperti dal ticket restaurant.\n- A partire dal 9 settembre 2024, l'indennità di trasferta non verrà riconosciuta in determinati casi, come durante gli eventi Summer e Winter Party o per spostamenti senza pernottamento.\n- Per ottenere l'indennità di trasferta, è necessario inserire 30€ per ogni giornata trascorsa fuori sede nell'Expense Report.\n- Per le trasferte effettuate con l'auto, sono previste modalità di rimborso specifiche, come il rimborso del carburante o il calcolo dei costi per chilometro percorsi.\n- L'azienda non è responsabile per eventuali incidenti o danni derivanti dall'utilizzo dell'auto personale durante la trasferta.\n\nSe hai bisogno di ulteriori informazioni o chiarimenti, non esitare a chiedere!"}]
```