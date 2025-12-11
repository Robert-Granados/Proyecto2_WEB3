# api/json_api_server.py

import io
import os
import json
import sys
from datetime import datetime, timezone
import tempfile
from typing import Optional

import requests
from PIL import Image
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_file
from fpdf import FPDF

ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(ROOT_DIR, "..")))

from db_utils import (
    deactivate_file_record,
    deactivate_product_record,
    update_file_record,
    update_product_record,
)

load_dotenv()

DATA_DIR = os.getenv("DATA_DIR", "data")

# Serve the frontend directly from the mounted folder
app = Flask(__name__, static_folder="../frontend", static_url_path="")


def load_json(filename: str):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def load_product_by_id(product_id: int):
    products = load_json("results.json")
    for product in products:
        if product.get("id") == product_id:
            return product
    return None


def _format_price_currency(price, currency):
    if price is None:
        return "-"
    try:
        valor = float(price)
    except (TypeError, ValueError):
        return "-"
    etiqueta = currency or ""
    return f"{valor:,.0f} {etiqueta}".strip()


def _draw_cover(pdf: FPDF):
    pdf.set_font("Arial", "B", 20)
    pdf.cell(0, 10, "Dashboard Web Scraping MercadoLibre Costa Rica", ln=True, align="C")
    pdf.set_font("Arial", "", 16)
    pdf.cell(0, 6, "Reporte de datos de scraping", ln=True, align="C")
    pdf.ln(6)
    pdf.set_font("Arial", "", 11)
    timestamp = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    pdf.cell(0, 6, f"Generado: {timestamp}", ln=True, align="L")
    pdf.ln(4)
    pdf.set_draw_color(180, 180, 200)
    pdf.set_line_width(0.5)
    current_y = pdf.get_y()
    pdf.line(pdf.l_margin, current_y, pdf.w - pdf.r_margin, current_y)
    pdf.ln(8)


def _build_summary_cards(pdf: FPDF, products: list[dict], files: list[dict], events: list[dict]):
    # Cuadros que representan los totales del dashboard (similares a las tarjetas)
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 8, "Resumen del dashboard", ln=True)
    pdf.ln(2)
    card_titles = [
        ("Total productos", len(products)),
        ("Productos activos", len([p for p in products if p.get("is_active")])),
        ("Archivos totales", len(files)),
        ("Eventos recientes", len(events)),
    ]
    width = (pdf.w - pdf.l_margin - pdf.r_margin - 15) / 4
    pdf.set_font("Arial", "", 10)
    for title, value in card_titles:
        pdf.set_fill_color(245, 245, 245)
        pdf.set_draw_color(200, 200, 200)
        pdf.cell(width, 25, "", border=1, ln=0, fill=True)
    pdf.ln(-25)
    for title, value in card_titles:
        pdf.set_font("Arial", "B", 16)
        pdf.cell(width, 12, str(value), border="LR", align="C")
    pdf.ln(12)
    for title, value in card_titles:
        pdf.set_font("Arial", "", 10)
        pdf.cell(width, 8, title, border="LRB", align="C")
    pdf.ln(12)


def _render_table(pdf: FPDF, headers: list[str], rows: list[list[str]], col_widths: list[float]):
    # Construimos cabecera y filas asegurando que la tabla se rompe correctamente entre paginas
    row_height = 7
    def print_header():
        pdf.set_font("Arial", "B", 10)
        pdf.set_fill_color(230, 230, 230)
        for idx, header in enumerate(headers):
            pdf.cell(col_widths[idx], row_height, header, border=1, fill=True, align="C")
        pdf.ln(row_height)

    print_header()

    pdf.set_font("Arial", "", 9)
    for row in rows:
        if pdf.get_y() > pdf.h - pdf.b_margin - row_height:
            pdf.add_page()
            print_header()
            pdf.set_font("Arial", "", 9)
        for idx, cell_value in enumerate(row):
            pdf.cell(col_widths[idx], row_height, cell_value, border=1)
        pdf.ln(row_height)
    pdf.ln(5)


def _build_products_table(pdf: FPDF, products: list[dict]):
    # Tabla detallada de productos con sus campos clave para consulta rapida
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 8, "Productos", ln=True)
    pdf.ln(2)
    headers = ["Nombre", "Marca", "Categoria", "Precio", "Estado", "Ultima vez visto", "URL"]
    widths = [50, 25, 30, 20, 20, 20, 25]
    rows = []
    for product in products:
        rows.append(
            [
                (product.get("name") or "-")[:35],
                product.get("brand") or "-",
                product.get("category") or "-",
                _format_price_currency(product.get("price"), product.get("currency")),
                "Activo" if product.get("is_active") else "Inactivo",
                product.get("last_seen_at") or "-",
                (product.get("url") or "-")[:45],
            ]
        )
    _render_table(pdf, headers, rows, widths)


def _build_files_table(pdf: FPDF, files: list[dict]):
    # Tabla visual de archivos con estado, hash y ruta
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 8, "Archivos", ln=True)
    pdf.ln(2)
    headers = ["Archivo", "Hash", "Estado", "Ultima vez visto", "Ruta / URL"]
    widths = [50, 50, 20, 25, 45]
    rows = []
    for file in files:
        rows.append(
            [
                file.get("filename") or "-",
                (file.get("hash") or "-")[:20],
                "Activo" if file.get("is_active") else "Inactivo",
                file.get("last_seen_at") or "-",
                file.get("url") or file.get("local_path") or "-",
            ]
        )
    _render_table(pdf, headers, rows, widths)


def _build_events_table(pdf: FPDF, events: list[dict]):
    # Tabla con los eventos recientes (limitada a los últimos 50 para mantener legibilidad)
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 8, "Eventos recientes", ln=True)
    pdf.ln(2)
    headers = ["Fecha y hora", "Tipo", "Descripcion", "ID relacionado"]
    widths = [45, 35, 75, 35]
    rows = []
    for event in events[:50]:
        rows.append(
            [
                event.get("created_at") or "-",
                event.get("event_type") or "-",
                (event.get("description") or "-")[:60],
                str(event.get("entity_id") or "-"),
            ]
        )
    _render_table(pdf, headers, rows, widths)


def _build_pdf(products: list[dict], files: list[dict], events: list[dict]) -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    _draw_cover(pdf)
    _build_summary_cards(pdf, products, files, events)
    _build_products_table(pdf, products)
    _build_files_table(pdf, files)
    _build_events_table(pdf, events)
    return pdf.output(dest="S").encode("latin-1")


def _download_image_to_temp(url: str) -> Optional[str]:
    if not url:
        return None

    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
    except requests.RequestException:
        return None

    suffix = os.path.splitext(url)[1] or ".jpg"
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        temp_file.write(resp.content)
        temp_file.flush()
    finally:
        temp_file.close()

    converted_path = temp_file.name
    try:
        with Image.open(temp_file.name) as img:
            fmt = (img.format or "").lower()
            if fmt not in {"jpeg", "jpg", "png"}:
                png_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
                try:
                    img.convert("RGB").save(png_temp.name, "PNG")
                finally:
                    png_temp.close()
                os.remove(temp_file.name)
                converted_path = png_temp.name
    except (OSError, Image.UnidentifiedImageError):
        pass

    return converted_path


def _build_product_detail_pdf(product: dict) -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Datos del producto", ln=True, align="C")
    pdf.ln(4)

    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, product.get("name") or "Producto desconocido", ln=True)
    image_path = _download_image_to_temp(product.get("image_url") or "")
    if image_path:
        try:
            display_width = pdf.w - pdf.l_margin - pdf.r_margin
            pdf.image(image_path, x=pdf.l_margin, w=display_width)
        except RuntimeError:
            pass
        finally:
            try:
                os.remove(image_path)
            except OSError:
                pass

    pdf.set_font("Arial", "", 11)
    fields = [
        ("Marca", product.get("brand") or "-"),
        ("Categoría", product.get("category") or "-"),
        ("Precio", _format_price_currency(product.get("price"), product.get("currency"))),
        ("URL", product.get("url") or "-"),
        ("Página", str(product.get("page") or "-")),
        ("Última vez visto", product.get("last_seen_at") or "-"),
        ("Estado", "Activo" if product.get("is_active") else "Inactivo"),
    ]
    for label, value in fields:
        pdf.set_font("Arial", "B", 11)
        pdf.cell(40, 8, f"{label}:", border=0)
        pdf.set_font("Arial", "", 11)
        pdf.multi_cell(0, 8, value, border=0)

    pdf.ln(4)
    pdf.set_font("Arial", "I", 10)
    pdf.cell(0, 6, f"Generado el {datetime.now(timezone.utc).astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}", ln=True)
    return pdf.output(dest="S").encode("latin-1")


@app.get("/api/products")
def get_products():
    return jsonify(load_json("results.json"))


@app.get("/api/files")
def get_files():
    return jsonify(load_json("files.json"))


@app.get("/api/events")
def get_events():
    return jsonify(load_json("events.json"))


@app.get("/api/export/pdf")
def export_pdf():
    products = load_json("results.json")
    files = load_json("files.json")
    events = load_json("events.json")
    pdf_bytes = _build_pdf(products, files, events)
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        download_name="reporte_scraper.pdf",
        as_attachment=True,
    )


@app.get("/api/export/products/<int:product_id>/pdf")
def export_product_pdf(product_id: int):
    product = load_product_by_id(product_id)
    if not product:
        return jsonify({"error": "Producto no encontrado"}), 404

    pdf_bytes = _build_product_detail_pdf(product)
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        download_name=f"producto_{product_id}.pdf",
        as_attachment=True,
    )


@app.put("/api/products/<int:product_id>")
def edit_product(product_id: int):
    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"error": "Se requiere un payload JSON válido"}), 400
    updated = update_product_record(product_id, payload)
    if updated is None:
        return jsonify({"error": "Producto no encontrado"}), 404
    return jsonify(updated)


@app.delete("/api/products/<int:product_id>")
def remove_product(product_id: int):
    success = deactivate_product_record(product_id)
    if not success:
        return jsonify({"error": "Producto no encontrado"}), 404
    return jsonify({"status": "eliminado", "id": product_id})


@app.put("/api/files/<int:file_id>")
def edit_file(file_id: int):
    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"error": "Se requiere un payload JSON válido"}), 400
    updated = update_file_record(file_id, payload)
    if updated is None:
        return jsonify({"error": "Archivo no encontrado"}), 404
    return jsonify(updated)


@app.delete("/api/files/<int:file_id>")
def remove_file(file_id: int):
    success = deactivate_file_record(file_id)
    if not success:
        return jsonify({"error": "Archivo no encontrado"}), 404
    return jsonify({"status": "eliminado", "id": file_id})


@app.get("/")
def index():
    # Return the SPA entrypoint
    return app.send_static_file("index.html")


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    host = os.getenv("FLASK_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_PORT", "5000"))
    debug = bool(int(os.getenv("FLASK_DEBUG", "0")))
    app.run(host=host, port=port, debug=debug)
