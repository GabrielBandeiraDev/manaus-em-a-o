import io

from PIL import Image

from regras import REGRAS, ErroReclamacao, preparar_foto, validar_campos


def _formulario(**troca):
    base = {
        "nome": "Ana Souza",
        "endereco": "Rua das Flores, 10",
        "descricao": "Cratera aberta na avenida há vários meses.",
    }
    base.update(troca)
    return base


def _png(largura=48, altura=48) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (largura, altura), (180, 20, 20)).save(buf, format="PNG")
    return buf.getvalue()


def test_regras_pedem_nome_endereco_problema_e_foto():
    texto = " ".join(REGRAS).lower()
    assert "foto" in texto
    assert "nome" in texto
    assert "endereço" in texto
    assert "problema" in texto
    assert "telefone" not in texto


def test_endereco_sem_numero_falha():
    try:
        validar_campos(_formulario(endereco="Rua sem numero"))
    except ErroReclamacao as exc:
        assert "número" in exc.mensagem
    else:
        raise AssertionError("endereço sem número passou")


def test_campos_validos_so_tem_nome_endereco_e_problema():
    dados = validar_campos(_formulario())
    assert dados == {
        "nome": "Ana Souza",
        "endereco": "Rua das Flores, 10",
        "descricao": "Cratera aberta na avenida há vários meses.",
    }


def test_foto_png_vira_jpeg_sem_exif():
    imagem = Image.new("RGB", (40, 40), (1, 2, 3))
    buf = io.BytesIO()
    exif = Image.Exif()
    exif[0x010F] = "telefone secreto 92999999999"
    imagem.save(buf, format="JPEG", exif=exif)
    tipo, extensao, limpa = preparar_foto(buf.getvalue())
    assert tipo == "image/jpeg"
    assert extensao == "jpg"
    assert limpa.startswith(b"\xff\xd8\xff")
    assert b"92999999999" not in limpa


def test_png_pequena_e_arquivo_falso_falham():
    try:
        preparar_foto(_png(16, 16))
    except ErroReclamacao as exc:
        assert "pequena" in exc.mensagem
    else:
        raise AssertionError("foto minúscula passou")

    try:
        preparar_foto(b"<svg xmlns='http://www.w3.org/2000/svg'></svg>")
    except ErroReclamacao as exc:
        assert "JPG" in exc.mensagem
    else:
        raise AssertionError("svg passou")


def test_png_de_tamanho_ok():
    tipo, extensao, limpa = preparar_foto(_png())
    assert tipo == "image/jpeg"
    assert extensao == "jpg"
    assert len(limpa) < 5 * 1024 * 1024
