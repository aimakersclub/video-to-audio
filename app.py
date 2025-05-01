from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, HttpUrl
import os
import uuid
import tempfile
import base64
import moviepy.editor as mp
from typing import Optional, Dict, Any, Union
import shutil
import whisper
import subprocess
import sys

app = FastAPI(title="Video to Audio Extractor API")

# Define uma rota para verificar o status do sistema
@app.get("/system-check")
async def check_system():
    """
    Verifica o estado do sistema, incluindo FFmpeg e o modelo Whisper.
    """
    system_status = {
        "status": "ok",
        "ffmpeg_installed": check_ffmpeg(),
        "whisper_model_loaded": "whisper_model" in globals(),
        "temp_directory": TEMP_DIR,
        "temp_directory_exists": os.path.exists(TEMP_DIR),
        "python_version": sys.version,
        "os_platform": sys.platform
    }
    
    # Adicionando informações adicionais se houver problemas
    if not system_status["ffmpeg_installed"]:
        system_status["status"] = "error"
        system_status["ffmpeg_installation_instructions"] = install_ffmpeg_instructions()
        
    if not system_status["whisper_model_loaded"]:
        system_status["status"] = "error"
        system_status["whisper_error"] = "Modelo Whisper não foi carregado corretamente"
        
    if not system_status["temp_directory_exists"]:
        system_status["status"] = "warning"
        system_status["temp_directory_error"] = "Diretório temporário não existe"
    
    return system_status

class VideoRequest(BaseModel):
    url: Optional[HttpUrl] = None
    base64_data: Optional[str] = None
    filename: Optional[str] = None
    
    class Config:
        schema_extra = {
            "example": {
                "url": "https://example.com/video.mp4",
                "base64_data": None,
                "filename": "my_video.mp4"
            }
        }

class AudioResponse(BaseModel):
    download_url: str
    base64_data: Optional[str] = None
    mimetype: str
    filename: str
    
    class Config:
        schema_extra = {
            "example": {
                "download_url": "/download/audio_12345.mp3",
                "base64_data": "base64_encoded_string_here",
                "mimetype": "audio/mp3",
                "filename": "my_video.mp3"
            }
        }

class TranscriptionResponse(BaseModel):
    transcription: str
    language: str
    audio_url: str
    
    class Config:
        schema_extra = {
            "example": {
                "transcription": "Este é um exemplo de transcrição de áudio.",
                "language": "pt",
                "audio_url": "/download/audio_12345.mp3"
            }
        }

# Ensure temp directory exists
TEMP_DIR = os.path.join(tempfile.gettempdir(), "audio_extractor")
os.makedirs(TEMP_DIR, exist_ok=True)

# Verificar se o FFmpeg está instalado
def check_ffmpeg():
    try:
        # Tenta executar ffmpeg -version para verificar se está instalado
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False

# Função para instalar FFmpeg em diferentes sistemas operacionais
def install_ffmpeg_instructions():
    if sys.platform.startswith('linux'):
        return "Instale o FFmpeg com: sudo apt-get update && sudo apt-get install -y ffmpeg"
    elif sys.platform == 'darwin':
        return "Instale o FFmpeg com: brew install ffmpeg"
    elif sys.platform == 'win32':
        return "Baixe o FFmpeg de https://ffmpeg.org/download.html ou instale com: choco install ffmpeg"
    else:
        return "Por favor, instale o FFmpeg manualmente de https://ffmpeg.org/download.html"

# Verificar FFmpeg e carregar o modelo Whisper
if not check_ffmpeg():
    print(f"ERRO: FFmpeg não encontrado. {install_ffmpeg_instructions()}")
    print("A API continuará funcionando, mas a transcrição pode falhar.")

# Load Whisper model - use "small" for a good balance of quality and speed
# Options: "tiny", "base", "small", "medium", "large"
try:
    whisper_model = whisper.load_model("small")
    print("Modelo Whisper carregado com sucesso.")
except Exception as e:
    print(f"Erro ao carregar o modelo Whisper: {e}")
    print("A API continuará funcionando, mas a transcrição pode falhar.")

@app.post("/extract-audio", response_model=AudioResponse)
async def extract_audio(video_request: VideoRequest = Body(...)):
    try:
        if not video_request.url and not video_request.base64_data:
            raise HTTPException(status_code=400, detail="Either URL or base64_data must be provided")
        
        # Generate unique filename if not provided
        original_filename = video_request.filename or "video"
        unique_id = str(uuid.uuid4())[:8]
        video_filename = f"{unique_id}_{original_filename}"
        video_path = os.path.join(TEMP_DIR, video_filename)
        
        # Process based on input type
        if video_request.url:
            # Download video from URL
            from urllib.request import urlretrieve
            urlretrieve(str(video_request.url), video_path)
        else:
            # Decode base64 data
            try:
                # Extract actual base64 data if it contains metadata
                if "," in video_request.base64_data:
                    base64_data = video_request.base64_data.split(",")[1]
                else:
                    base64_data = video_request.base64_data
                    
                video_data = base64.b64decode(base64_data)
                with open(video_path, "wb") as f:
                    f.write(video_data)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid base64 data: {str(e)}")
        
        # Extract audio
        audio_filename = os.path.splitext(video_filename)[0] + ".mp3"
        audio_path = os.path.join(TEMP_DIR, audio_filename)
        
        try:
            video = mp.VideoFileClip(video_path)
            video.audio.write_audiofile(audio_path)
            video.close()
        except Exception as e:
            # Clean up files
            if os.path.exists(video_path):
                os.remove(video_path)
            raise HTTPException(status_code=500, detail=f"Audio extraction failed: {str(e)}")
        
        # Clean up video file
        if os.path.exists(video_path):
            os.remove(video_path)
        
        # Create response
        download_url = f"/download/{audio_filename}"
        
        # Create base64 data for response
        with open(audio_path, "rb") as audio_file:
            audio_data = audio_file.read()
            base64_audio = base64.b64encode(audio_data).decode("utf-8")
        
        return AudioResponse(
            download_url=download_url,
            base64_data=base64_audio,
            mimetype="audio/mp3",
            filename=audio_filename
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@app.get("/download/{filename}")
async def download_audio(filename: str):
    file_path = os.path.join(TEMP_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=file_path,
        media_type="audio/mp3",
        filename=filename
    )

@app.post("/transcribe-audio", response_model=TranscriptionResponse)
async def transcribe_audio(video_request: VideoRequest = Body(...)):
    """
    Extrai o áudio de um vídeo e transcreve o conteúdo falado.
    """
    try:
        # Primeiro extraímos o áudio usando a mesma lógica do endpoint extract-audio
        if not video_request.url and not video_request.base64_data:
            raise HTTPException(status_code=400, detail="Either URL or base64_data must be provided")
        
        # Generate unique filename if not provided
        original_filename = video_request.filename or "video"
        unique_id = str(uuid.uuid4())[:8]
        video_filename = f"{unique_id}_{original_filename}"
        video_path = os.path.join(TEMP_DIR, video_filename)
        
        # Process based on input type
        if video_request.url:
            # Download video from URL
            from urllib.request import urlretrieve
            urlretrieve(str(video_request.url), video_path)
        else:
            # Decode base64 data
            try:
                # Extract actual base64 data if it contains metadata
                if "," in video_request.base64_data:
                    base64_data = video_request.base64_data.split(",")[1]
                else:
                    base64_data = video_request.base64_data
                    
                video_data = base64.b64decode(base64_data)
                with open(video_path, "wb") as f:
                    f.write(video_data)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid base64 data: {str(e)}")
        
        # Extract audio
        audio_filename = os.path.splitext(video_filename)[0] + ".mp3"
        audio_path = os.path.join(TEMP_DIR, audio_filename)
        
        try:
            video = mp.VideoFileClip(video_path)
            video.audio.write_audiofile(audio_path)
            video.close()
        except Exception as e:
            # Clean up files
            if os.path.exists(video_path):
                os.remove(video_path)
            raise HTTPException(status_code=500, detail=f"Audio extraction failed: {str(e)}")
        
        # Clean up video file
        if os.path.exists(video_path):
            os.remove(video_path)
            
        # Realizar a transcrição do áudio usando o Whisper
        try:
            # Verificar novamente se o FFmpeg está instalado antes de tentar a transcrição
            if not check_ffmpeg():
                raise Exception(f"FFmpeg não está instalado. {install_ffmpeg_instructions()}")
                
            # Verificar se o arquivo existe
            if not os.path.exists(audio_path):
                raise Exception(f"Arquivo de áudio não encontrado: {audio_path}")
                
            print(f"Iniciando transcrição do arquivo: {audio_path}")
            
            # Configurar a transcrição com opções específicas
            result = whisper_model.transcribe(
                audio_path,
                fp16=False,  # Desativar fp16 pode ajudar em alguns sistemas
                verbose=True  # Ativar logs verbosos para depuração
            )
            
            transcription = result["text"]
            detected_language = result["language"]
            
            print(f"Transcrição concluída. Idioma detectado: {detected_language}")
            
            # Criar URL de download para o áudio
            download_url = f"/download/{audio_filename}"
            
            return TranscriptionResponse(
                transcription=transcription,
                language=detected_language,
                audio_url=download_url
            )
            
        except Exception as e:
            error_message = str(e)
            print(f"Erro de transcrição: {error_message}")
            
            # Verificar erros específicos e fornecer mensagens mais úteis
            if "No such file or directory: 'ffmpeg'" in error_message:
                error_message = f"FFmpeg não encontrado. Por favor, instale o FFmpeg: {install_ffmpeg_instructions()}"
            elif "audio_path" in error_message and "does not exist" in error_message:
                error_message = f"O arquivo de áudio não foi encontrado ou não pôde ser processado corretamente."
                
            raise HTTPException(status_code=500, detail=f"Falha na transcrição: {error_message}")
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@app.post("/extract-and-transcribe", response_model=Dict[str, Any])
async def extract_and_transcribe(video_request: VideoRequest = Body(...)):
    """
    Endpoint combinado para extrair o áudio e transcrever em uma única requisição.
    Retorna tanto os dados do áudio quanto a transcrição.
    """
    try:
        # Extrair o áudio
        audio_response = await extract_audio(video_request)
        
        # Realizar a transcrição
        # Usamos o caminho do arquivo diretamente, já que ele foi gerado na etapa anterior
        audio_filename = audio_response.filename
        audio_path = os.path.join(TEMP_DIR, audio_filename)
        
        # Realizar a transcrição do áudio usando o Whisper
        try:
            # Verificar novamente se o FFmpeg está instalado antes de tentar a transcrição
            if not check_ffmpeg():
                raise Exception(f"FFmpeg não está instalado. {install_ffmpeg_instructions()}")
                
            # Verificar se o arquivo existe
            if not os.path.exists(audio_path):
                raise Exception(f"Arquivo de áudio não encontrado: {audio_path}")
                
            print(f"Iniciando transcrição do arquivo: {audio_path}")
            
            # Configurar a transcrição com opções específicas
            result = whisper_model.transcribe(
                audio_path,
                fp16=False,  # Desativar fp16 pode ajudar em alguns sistemas
                verbose=True  # Ativar logs verbosos para depuração
            )
            
            transcription = result["text"]
            detected_language = result["language"]
            
            print(f"Transcrição concluída. Idioma detectado: {detected_language}")
            
            # Combinar os resultados
            return {
                "audio": {
                    "download_url": audio_response.download_url,
                    "base64_data": audio_response.base64_data,
                    "mimetype": audio_response.mimetype,
                    "filename": audio_response.filename
                },
                "transcription": {
                    "text": transcription,
                    "language": detected_language
                }
            }
            
        except Exception as e:
            error_message = str(e)
            print(f"Erro de transcrição: {error_message}")
            
            # Verificar erros específicos e fornecer mensagens mais úteis
            if "No such file or directory: 'ffmpeg'" in error_message:
                error_message = f"FFmpeg não encontrado. Por favor, instale o FFmpeg: {install_ffmpeg_instructions()}"
            elif "audio_path" in error_message and "does not exist" in error_message:
                error_message = f"O arquivo de áudio não foi encontrado ou não pôde ser processado corretamente."
                
            # Retorna pelo menos os dados de áudio mesmo se a transcrição falhar
            return {
                "audio": {
                    "download_url": audio_response.download_url,
                    "base64_data": audio_response.base64_data,
                    "mimetype": audio_response.mimetype,
                    "filename": audio_response.filename
                },
                "transcription": {
                    "error": error_message,
                    "text": "Falha na transcrição. Verifique o erro para mais detalhes.",
                    "language": "unknown"
                }
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

# Cleanup task to remove old files
@app.on_event("startup")
async def startup_event():
    print("Starting cleanup task")

# Run a periodic cleanup task to remove files older than 1 hour
@app.on_event("shutdown")
async def shutdown_event():
    print("Cleaning up temporary files")
    try:
        shutil.rmtree(TEMP_DIR)
        os.makedirs(TEMP_DIR, exist_ok=True)
    except Exception as e:
        print(f"Error during cleanup: {str(e)}")


class AudioMixRequest(BaseModel):
    audio: Optional[str] = None
    audio_base64: Optional[str] = None
    wait_music: int = 0
    music: Optional[str] = None
    music_base64: Optional[str] = None
    fade_end_at: int = 0
    
    class Config:
        schema_extra = {
            "example": {
                "audio": "narration.mp3",
                "audio_base64": "base64_encoded_narration",
                "wait_music": 3,
                "music": "background.mp3",
                "music_base64": "base64_encoded_music",
                "fade_end_at": 4
            }
        }

class AudioMixResponse(BaseModel):
    download_url: str
    base64_data: Optional[str] = None
    mimetype: str
    filename: str
    
    class Config:
        schema_extra = {
            "example": {
                "download_url": "/download/mixed_12345.mp3",
                "base64_data": "base64_encoded_string_here",
                "mimetype": "audio/mp3",
                "filename": "mixed_audio.mp3"
            }
        }

@app.post("/mix-audio", response_model=AudioMixResponse)
async def mix_audio(mix_request: AudioMixRequest = Body(...)):
    """
    Combina um áudio de narração com música de fundo.
    A narração começa após o tempo especificado em wait_music.
    Após o término da narração, espera o tempo fade_end_at e aplica um fadeout na música.
    """
    try:
        # Validação de entradas
        if (not mix_request.audio and not mix_request.audio_base64) or \
           (not mix_request.music and not mix_request.music_base64):
            raise HTTPException(
                status_code=400, 
                detail="É necessário fornecer tanto o áudio de narração quanto a música de fundo"
            )
        
        # Gerar nomes de arquivos únicos
        unique_id = str(uuid.uuid4())[:8]
        narration_filename = f"narration_{unique_id}.mp3"
        music_filename = f"music_{unique_id}.mp3"
        output_filename = f"mixed_{unique_id}.mp3"
        
        narration_path = os.path.join(TEMP_DIR, narration_filename)
        music_path = os.path.join(TEMP_DIR, music_filename)
        output_path = os.path.join(TEMP_DIR, output_filename)
        
        # Processamento do áudio de narração
        if mix_request.audio_base64:
            try:
                # Extract actual base64 data if it contains metadata
                if "," in mix_request.audio_base64:
                    base64_data = mix_request.audio_base64.split(",")[1]
                else:
                    base64_data = mix_request.audio_base64
                    
                audio_data = base64.b64decode(base64_data)
                with open(narration_path, "wb") as f:
                    f.write(audio_data)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Dados base64 inválidos para áudio: {str(e)}")
        elif mix_request.audio:
            # Verificar se o arquivo existe no diretório temp
            source_path = os.path.join(TEMP_DIR, mix_request.audio)
            if not os.path.exists(source_path):
                raise HTTPException(status_code=404, detail=f"Arquivo de áudio '{mix_request.audio}' não encontrado")
            # Copiar o arquivo para o novo caminho
            shutil.copy(source_path, narration_path)
        
        # Processamento da música de fundo
        if mix_request.music_base64:
            try:
                # Extract actual base64 data if it contains metadata
                if "," in mix_request.music_base64:
                    base64_data = mix_request.music_base64.split(",")[1]
                else:
                    base64_data = mix_request.music_base64
                    
                music_data = base64.b64decode(base64_data)
                with open(music_path, "wb") as f:
                    f.write(music_data)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Dados base64 inválidos para música: {str(e)}")
        elif mix_request.music:
            # Verificar se o arquivo existe no diretório temp
            source_path = os.path.join(TEMP_DIR, mix_request.music)
            if not os.path.exists(source_path):
                raise HTTPException(status_code=404, detail=f"Arquivo de música '{mix_request.music}' não encontrado")
            # Copiar o arquivo para o novo caminho
            shutil.copy(source_path, music_path)
        
        # Carregar os arquivos de áudio com MoviePy
        try:
            narration_audio = mp.AudioFileClip(narration_path)
            music_audio = mp.AudioFileClip(music_path)
            
            # Calcular duração total necessária
            narration_duration = narration_audio.duration
            fadeout_duration = 3.0  # Duração do fadeout em segundos
            total_duration = mix_request.wait_music + narration_duration + mix_request.fade_end_at + fadeout_duration
            
            # Verifique se a música é longa o suficiente, caso contrário, faça um loop
            if music_audio.duration < total_duration:
                # Para evitar problemas com o loop, vamos usar ffmpeg para concatenar a música 
                # várias vezes em um novo arquivo
                temp_extended_music = os.path.join(TEMP_DIR, f"extended_{music_filename}")
                loops_needed = int(total_duration / music_audio.duration) + 1
                
                # Fechamos o clip para evitar problemas com arquivos abertos
                music_audio.close()
                
                # Usar FFmpeg diretamente para duplicar o arquivo várias vezes
                cmd = [
                    "ffmpeg", "-y",
                    "-stream_loop", str(loops_needed - 1),
                    "-i", music_path,
                    "-c", "copy",
                    temp_extended_music
                ]
                subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # Reabrir o arquivo estendido
                music_audio = mp.AudioFileClip(temp_extended_music)
            
            # Reduzir o volume da música para não sobrepor a narração
            background_volume = 0.3  # 30% do volume original
            music_audio = music_audio.volumex(background_volume)
            
            # Cortar a música para a duração total necessária
            music_audio = music_audio.subclip(0, total_duration)
            
            # Criar o arquivo da narração com delay
            # Primeiro criamos um arquivo de silêncio para o início
            silence_path = os.path.join(TEMP_DIR, f"silence_{unique_id}.mp3")
            cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi",
                "-i", f"anullsrc=r=44100:cl=stereo:d={mix_request.wait_music}",
                "-acodec", "libmp3lame",
                silence_path
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Concatenamos o silêncio + narração para criar o áudio com delay
            silence_audio = mp.AudioFileClip(silence_path)
            narration_with_delay = mp.concatenate_audioclips([silence_audio, narration_audio])
            
            # Determinar o ponto de início do fadeout
            fadeout_point = mix_request.wait_music + narration_duration + mix_request.fade_end_at
            
            # Aplicar fadeout usando ffmpeg em um arquivo temporário
            music_with_fadeout_path = os.path.join(TEMP_DIR, f"music_fadeout_{unique_id}.mp3")
            
            # Primeiro salvamos a música sem fadeout
            music_without_fadeout_path = os.path.join(TEMP_DIR, f"music_no_fadeout_{unique_id}.mp3")
            music_audio.write_audiofile(music_without_fadeout_path, fps=44100, nbytes=2, codec='libmp3lame')
            
            # Fechamos para liberar recursos
            music_audio.close()
            
            # Aplicamos o fadeout com FFmpeg
            cmd = [
                "ffmpeg", "-y",
                "-i", music_without_fadeout_path,
                "-af", f"afade=t=out:st={fadeout_point}:d={fadeout_duration}",
                music_with_fadeout_path
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Recarregar o áudio com fadeout
            music_with_fadeout = mp.AudioFileClip(music_with_fadeout_path)
            
            # Combinar os dois áudios
            final_audio = mp.CompositeAudioClip([music_with_fadeout, narration_with_delay])
            final_audio = final_audio.set_duration(total_duration)
            
            # Salvar o resultado final
            final_audio.write_audiofile(output_path, fps=44100, nbytes=2, codec='libmp3lame')
            
            # Limpar arquivos temporários
            for path in [narration_path, music_path, silence_path, 
                         music_without_fadeout_path, music_with_fadeout_path]:
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except:
                        pass
            
            # Se criamos um arquivo de música estendido, vamos limpar também
            if 'temp_extended_music' in locals() and os.path.exists(temp_extended_music):
                try:
                    os.remove(temp_extended_music)
                except:
                    pass
            
            # Criar URL de download e dados base64 para resposta
            download_url = f"/download/{output_filename}"
            
            with open(output_path, "rb") as audio_file:
                audio_data = audio_file.read()
                base64_audio = base64.b64encode(audio_data).decode("utf-8")
            
            return AudioMixResponse(
                download_url=download_url,
                base64_data=base64_audio,
                mimetype="audio/mp3",
                filename=output_filename
            )
            
        except Exception as e:
            # Limpar arquivos em caso de erro
            for path in [narration_path, music_path, output_path]:
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except:
                        pass
            # Se temos arquivos temporários adicionais, limpar também
            temp_files = [
                f"silence_{unique_id}.mp3", 
                f"music_fadeout_{unique_id}.mp3",
                f"music_no_fadeout_{unique_id}.mp3",
                f"extended_{music_filename}"
            ]
            for filename in temp_files:
                path = os.path.join(TEMP_DIR, filename)
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except:
                        pass
            
            raise HTTPException(status_code=500, detail=f"Erro ao processar áudio: {str(e)}")
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro do servidor: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))