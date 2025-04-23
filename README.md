# Video to Audio Extractor e Transcrição API

Uma API simples para extrair áudio de arquivos de vídeo e transcrever o conteúdo falado, seja por URL ou base64.

## Funcionalidades

- Extrair áudio de vídeos a partir de uma URL
- Extrair áudio de vídeos a partir de dados em base64
- Retornar a URL para download do áudio
- Retornar o áudio em formato base64
- Transcrever o conteúdo falado no áudio
- Detectar automaticamente o idioma da fala
- Realizar extração e transcrição em uma única requisição

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

### Endpoints Principais

#### Extração de Áudio
```
POST /extract-audio
```

#### Transcrição de Áudio
```
POST /transcribe-audio
```

#### Extração e Transcrição Combinadas
```
POST /extract-and-transcribe
```

### Parâmetros

Todos os endpoints aceitam um objeto JSON com os seguintes campos:

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

### Respostas

#### Extração de Áudio

```json
{
  "download_url": "/download/audio_12345.mp3",
  "base64_data": "base64_encoded_string_here",
  "mimetype": "audio/mp3",
  "filename": "meu_video.mp3"
}
```

#### Transcrição de Áudio

```json
{
  "transcription": "Este é um exemplo de transcrição de áudio.",
  "language": "pt",
  "audio_url": "/download/audio_12345.mp3"
}
```

#### Extração e Transcrição Combinadas

```json
{
  "audio": {
    "download_url": "/download/audio_12345.mp3",
    "base64_data": "base64_encoded_string_here",
    "mimetype": "audio/mp3",
    "filename": "meu_video.mp3"
  },
  "transcription": {
    "text": "Este é um exemplo de transcrição de áudio.",
    "language": "pt"
  }
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
- OpenAI Whisper
- PyTorch

## Modelos de Transcrição

A API utiliza o modelo Whisper para transcrição de áudio. Por padrão, usa o modelo "small" que oferece um bom equilíbrio entre qualidade e velocidade. Você pode modificar o código para usar outros modelos:

- **tiny**: Mais rápido, menor precisão
- **base**: Rápido com precisão média
- **small**: Equilíbrio entre velocidade e precisão
- **medium**: Alta precisão, mais lento
- **large**: Melhor precisão, mais recursos de hardware

## Limitações

- Os arquivos temporários são armazenados no servidor e limpos periodicamente
- O tamanho máximo do arquivo pode ser limitado pela configuração do servidor
- A transcrição pode consumir mais recursos computacionais dependendo do tamanho do áudio
- O modelo Whisper precisa ser baixado na primeira execução (~1GB para o modelo "small")

## Resolução de Problemas

### Erro: "FFmpeg não encontrado"

Se você encontrar o erro `"[Errno 2] No such file or directory: 'ffmpeg'"`, isso significa que o FFmpeg não está instalado ou não está no PATH do sistema. Para corrigir:

#### Linux (Ubuntu/Debian):
```
sudo apt-get update && sudo apt-get install -y ffmpeg
```

#### Mac (com Homebrew):
```
brew install ffmpeg
```

#### Windows:
- Baixe do [site oficial do FFmpeg](https://ffmpeg.org/download.html)
- Ou use Chocolatey: `choco install ffmpeg`
- Adicione o FFmpeg ao PATH do sistema

#### Verificando a instalação:
Após instalar, execute `ffmpeg -version` para confirmar que está funcionando.

### Verificação do Sistema

A API inclui um endpoint `/system-check` que pode ser usado para diagnosticar problemas:

```
GET /system-check
```

Este endpoint retorna informações sobre o estado do sistema, incluindo se o FFmpeg está instalado corretamente.