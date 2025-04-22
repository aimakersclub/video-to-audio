# Video to Audio Extractor API

Uma API simples para extrair áudio de arquivos de vídeo, seja por URL ou base64.

## Funcionalidades

- Extrair áudio de vídeos a partir de uma URL
- Extrair áudio de vídeos a partir de dados em base64
- Retornar a URL para download do áudio
- Retornar o áudio em formato base64

## Instalação e Execução

### Usando Docker

1. Clone o repositório
2. Construa a imagem Docker:
   ```
   docker build -t video-audio-extractor .
   ```
3. Execute o contêiner:
   ```
   docker run -p 8000:8000 video-audio-extractor
   ```

### Instalação Local

1. Clone o repositório
2. Instale as dependências:
   ```
   pip install -r requirements.txt
   ```
3. Execute a aplicação:
   ```
   uvicorn app:app --reload
   ```

## Uso da API

### Endpoint Principal

```
POST /extract-audio
```

### Parâmetros

A API aceita um objeto JSON com os seguintes campos:

- `url`: URL do arquivo de vídeo (opcional)
- `base64_data`: String codificada em base64 do arquivo de vídeo (opcional)
- `filename`: Nome do arquivo (opcional)

Pelo menos um dos parâmetros `url` ou `base64_data` deve ser fornecido.

### Exemplos de Requisição

#### Usando URL

```json
{
  "url": "https://example.com/video.mp4",
  "filename": "meu_video.mp4"
}
```

#### Usando Base64

```json
{
  "base64_data": "data:video/mp4;base64,AAAAIGZ0eXBpc29tAAACAGlzb21pc28yYXZjMW1wNDEAAAAIZnJlZQAAA7...",
  "filename": "meu_video.mp4"
}
```

### Resposta

A API retorna um objeto JSON com os seguintes campos:

```json
{
  "download_url": "/download/audio_12345.mp3",
  "base64_data": "base64_encoded_string_here",
  "mimetype": "audio/mp3",
  "filename": "meu_video.mp3"
}
```

### Download do Áudio

Para baixar o arquivo de áudio, acesse:

```
GET /download/{filename}
```

## Deploy

### Heroku

A aplicação inclui um Procfile para deploy no Heroku. Para fazer o deploy:

1. Crie uma aplicação no Heroku
2. Adicione o buildpack do Python
3. Envie o código para o Heroku
4. A aplicação estará disponível em `https://sua-aplicacao.herokuapp.com`

## Requisitos

- Python 3.9+
- FastAPI
- MoviePy
- FFmpeg

## Limitações

- Os arquivos temporários são armazenados no servidor e limpos periodicamente
- O tamanho máximo do arquivo pode ser limitado pela configuração do servidor