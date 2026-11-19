"""Regras da reclamação: nome, endereço, problema e foto."""

from __future__ import annotations

import io
import unicodedata

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_FOTO = 5 * 1024 * 1024
MAX_LADO = 2000

REGRAS = (
    "Diz seu nome. Ele sai na notícia.",
    "Endereço com rua e número, do lugar do problema. Ele sai na notícia.",
    "Descreve o problema com clareza, em pelo menos uma frase.",
    "A foto é obrigatória, do problema no local, nítida, sem montagem e sem ofensa. Até 5 MB, JPG, PNG ou WEBP.",
)

Image.MAX_IMAGE_PIXELS = 24_000_000


class ErroReclamacao(Exception):
    def __init__(self, mensagem: str, status: int = 400) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.status = status


def _texto(form: dict, chave: str) -> str:
    valor = form.get(chave, "")
    if not isinstance(valor, str):
        return ""
    return valor.strip()


def _linha(valor: str) -> str:
    return " ".join(valor.split())


def _tem_letra(valor: str) -> bool:
    return any(unicodedata.category(caractere).startswith("L") for caractere in valor)


def validar_campos(form: dict) -> dict:
    nome = _linha(_texto(form, "nome"))
    if not 3 <= len(nome) <= 80 or not _tem_letra(nome) or any(c.isdigit() for c in nome):
        raise ErroReclamacao("Diz seu nome. Sem número.")

    endereco = _linha(_texto(form, "endereco"))
    if not 8 <= len(endereco) <= 180:
        raise ErroReclamacao("Endereço com rua e número.")
    if not any(c.isdigit() for c in endereco) and "s/n" not in endereco.lower():
        raise ErroReclamacao("Coloca o número do endereço, ou s/n.")

    descricao = _texto(form, "descricao").replace("\r\n", "\n").replace("\r", "\n")
    if not 20 <= len(descricao) <= 800:
        raise ErroReclamacao("Descreve o problema numa frase. Mínimo de 20 caracteres, máximo de 800.")

    return {
        "nome": nome,
        "endereco": endereco,
        "descricao": descricao,
    }


def _magic(conteudo: bytes) -> str:
    if conteudo.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if conteudo.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(conteudo) >= 12 and conteudo[:4] == b"RIFF" and conteudo[8:12] == b"WEBP":
        return "image/webp"
    raise ErroReclamacao("A foto tem que ser JPG, PNG ou WEBP.")


def _codificar(img: Image.Image) -> tuple[str, str, bytes]:
    if img.mode not in ("RGB", "L"):
        base = img.convert("RGB")
    else:
        base = img
    ultimo = b""
    for qualidade in (85, 70, 55):
        buf = io.BytesIO()
        base.save(buf, format="JPEG", quality=qualidade, optimize=True)
        ultimo = buf.getvalue()
        if len(ultimo) <= MAX_FOTO:
            return "image/jpeg", "jpg", ultimo
    raise ErroReclamacao("A foto passa de 5 MB mesmo reduzida. Tira outra mais de perto.")


def preparar_foto(conteudo: bytes) -> tuple[str, str, bytes]:
    if not conteudo:
        raise ErroReclamacao("Manda a foto do problema.")
    if len(conteudo) > MAX_FOTO:
        raise ErroReclamacao("A foto passa de 5 MB. Tira outra mais leve.")
    _magic(conteudo)
    try:
        img = Image.open(io.BytesIO(conteudo))
        img.load()
        if getattr(img, "n_frames", 1) > 1:
            raise ErroReclamacao("Manda uma foto parada, sem animação.")
        img = ImageOps.exif_transpose(img)
        img.thumbnail((MAX_LADO, MAX_LADO))
        if img.width < 32 or img.height < 32:
            raise ErroReclamacao("A foto está pequena demais. Chega mais perto do problema.")
    except ErroReclamacao:
        raise
    except Image.DecompressionBombError as exc:
        raise ErroReclamacao("A foto é grande demais em pixels.") from exc
    except (UnidentifiedImageError, OSError) as exc:
        raise ErroReclamacao("A foto está corrompida ou não é uma imagem de verdade.") from exc
    return _codificar(img)
