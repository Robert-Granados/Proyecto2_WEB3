# Guía de Inicio Rápido

## Introducción

### Qué es el Proyecto
Este proyecto es una plataforma de scraping web avanzado que extrae datos de productos desde MercadoLibre Costa Rica. Recopila información como precios, imágenes y archivos relacionados, los almacena en una base de datos y los muestra en un dashboard web interactivo.

### Para Qué Sirve Esta Guía
Esta guía te permite configurar y ejecutar el proyecto desde cero en tu computadora local. Está diseñada para personas sin conocimientos avanzados en scraping, bases de datos o desarrollo web. Sigue los pasos en orden para evitar errores.

## Requisitos Previos

Antes de comenzar, asegúrate de tener instalados los siguientes programas:

- **Python 3.12 o superior**: Lenguaje de programación principal. Descárgalo desde python.org.
- **PostgreSQL 16**: Sistema de base de datos. Instálalo desde postgresql.org.
- **Git**: Herramienta para clonar repositorios. Instálalo desde git-scm.com.

Verifica las versiones con estos comandos:
```bash
python --version
psql --version
git --version
```

## Clonar el Repositorio

1. Abre una terminal o línea de comandos.
2. Navega a la carpeta donde quieres guardar el proyecto.
3. Ejecuta el comando para clonar el repositorio:

```bash
git clone https://github.com/Robert-Granados/Proyecto2_WEB3.git
```

4. Entra al directorio del proyecto:

```bash
cd Proyecto2_WEB3
```

## Configuración Inicial

### Crear Entorno Virtual
Un entorno virtual aísla las dependencias del proyecto.

1. Crea el entorno virtual:

```bash
python -m venv venv
```

### Activar Entorno Virtual
2. Activa el entorno virtual:

En Windows:
```bash
venv\Scripts\activate
```

En Linux/Mac:
```bash
source venv/bin/activate
```

### Instalar Dependencias
3. Instala las librerías necesarias:

```bash
pip install -r requirements.txt
```

## Configuración del Archivo .env

El archivo `.env` contiene configuraciones importantes. Crea un archivo llamado `.env` en la raíz del proyecto y agrega estas variables con tus valores:

- `POSTGRES_DB=scraper_db`: Nombre de la base de datos.
- `POSTGRES_USER=tu_usuario`: Usuario de PostgreSQL.
- `POSTGRES_PASSWORD=tu_contraseña`: Contraseña del usuario.
- `SCRAPER_CATEGORY_URL=https://listado.mercadolibre.co.cr/computacion`: URL de la categoría a scrapear.
- `SCRAPER_MAX_PAGES=3`: Número máximo de páginas a scrapear.
- `SCRAPER_USER_AGENT=Mozilla/5.0 (compatible; ScraperBot/1.0)`: Identificador para las peticiones web.
- `ENABLE_DYNAMIC_SCRAPER=0`: Activa scraping dinámico (0 = desactivado, 1 = activado).
- `DOWNLOADS_DIR=downloads`: Carpeta para archivos descargados.
- `STATIC_FILE_URLS=`: URLs de archivos estáticos (opcional).
- `DATA_DIR=data`: Carpeta para datos JSON.
- `SCHEDULER_INTERVAL_MINUTES=60`: Intervalo en minutos para scraping automático.
- `OPENAI_API_KEY=tu_clave_openai`: Clave de OpenAI (opcional para IA).
- `OPENAI_MODEL=gpt-4o-mini`: Modelo de IA a usar.
- `CHROME_BIN=/usr/bin/chromium`: Ruta a Chromium (para scraping dinámico).

Cada variable controla una parte del sistema. Ajusta los valores según tu configuración local.

## Preparación de la Base de Datos

### Crear Base de Datos
1. Abre PostgreSQL (psql) como administrador.
2. Crea la base de datos:

```sql
CREATE DATABASE scraper_db;
```

3. Crea un usuario y asigna permisos:

```sql
CREATE USER tu_usuario WITH PASSWORD 'tu_contraseña';
GRANT ALL PRIVILEGES ON DATABASE scraper_db TO tu_usuario;
```

### Restaurar Backup o Script SQL
4. Ejecuta el script para crear las tablas:

```bash
psql -U tu_usuario -d scraper_db -f sql/db_schema.sql
```

## Ejecución del Sistema

### Ejecutar Scraping Manual
Para ejecutar el scraping una vez:

```bash
python main.py
```

### Ejecutar el Scheduler
Para scraping automático cada 60 minutos:

```bash
python scheduler.py
```

### Ejecutar la API
Para iniciar el servidor web:

```bash
python api/json_api_server.py
```

El sistema estará disponible en http://localhost:5000.

## Visualización de Resultados

### Cómo Acceder al Dashboard
1. Abre un navegador web.
2. Ve a http://localhost:5000.
3. El dashboard muestra productos scrapeados, calendario de eventos y archivos.

### Qué Información se Puede Ver
- Lista de productos con precios e imágenes.
- Eventos de cambios en productos o archivos.
- Calendario interactivo con FullCalendar.
- Opción para descargar reportes en PDF.

## Solución de Problemas Comunes

- **Error: "Module not found"**: Activa el entorno virtual y reinstala dependencias con `pip install -r requirements.txt`.
- **Error de conexión a base de datos**: Verifica las variables en .env y que PostgreSQL esté corriendo.
- **Scraping no funciona**: Comprueba la URL en SCRAPER_CATEGORY_URL y tu conexión a internet.
- **API no responde**: Asegúrate de que el puerto 5000 esté libre y que el servidor esté ejecutándose.
- **Problemas con Docker**: Si usas Docker, verifica que los volúmenes estén montados correctamente.

Si encuentras errores, revisa los logs en la carpeta `logs/`.

## Cierre

### Recomendaciones Finales
- Ejecuta el scraping manual primero para probar.
- Monitorea los logs para detectar problemas.
- No modifiques el código sin entender los cambios.
- Para desarrollo avanzado, estudia la documentación de Flask, PostgreSQL y Selenium.
- Recuerda respetar los términos de servicio de las páginas scrapeadas.