FROM python:3.10-bullseye

# Installa i pacchetti di sistema necessari
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends postgresql-client \
    && apt-get update && apt-get install -y xdg-utils \
    && apt-get clean -y && rm -rf /var/lib/apt/lists/*

# Aggiorna pip
RUN python -m pip install --upgrade pip

# Imposta la directory di lavoro
WORKDIR /app

# Copia i file di dipendenze
COPY requirements.txt .
COPY pyproject.toml .

# Installa le dipendenze Python
RUN python -m pip install --no-cache-dir -r requirements.txt

# Copia tutto il codice dell'applicazione
COPY . /app

# Converti le terminazioni di riga da Windows (CRLF) a Unix (LF) e rendi eseguibile
RUN sed -i 's/\r$//' entrypoint.sh && chmod +x entrypoint.sh

# Esponi la porta 8000
EXPOSE 8000

# Comando di avvio
CMD ["bash", "-c", "./entrypoint.sh"]
