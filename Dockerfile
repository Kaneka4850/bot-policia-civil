# Usar a imagem oficial do Python 3.13
FROM python:3.13-slim

# Definir o diretório de trabalho no container
WORKDIR /app

# Copiar os arquivos de requisitos para o container
COPY requirements.txt .

# Instalar as dependências
RUN pip install --no-cache-dir -r requirements.txt

# Copiar o resto do código do bot para o container
COPY . .

# Comando para rodar o bot
CMD ["python", "main.py"]
