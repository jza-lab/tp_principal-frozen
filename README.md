# Sistema de Gestión de Producción - FrozenProd

Este es un sistema de gestión de producción desarrollado en Flask, diseñado para administrar insumos, órdenes de producción, reportes y más.

## Requisitos Previos

Asegúrate de tener instalado Python 3 en tu sistema. Puedes descargarlo desde [python.org](https://www.python.org/downloads/).

## Guía de Inicio Rápido

Sigue estos pasos para configurar y ejecutar el proyecto en tu entorno local.

### 1. Clona el Repositorio (Opcional)

Si estás trabajando con `git`, clona el repositorio. Si ya tienes los archivos, puedes saltar este paso.

```bash
git clone <URL_DEL_REPOSITORIO>
cd tp_principal-frozen
```

### 2. Instala las Dependencias

Instala todas las librerías de Python necesarias que se encuentran en el archivo `requirements.txt`.

```bash
pip install -r requirements.txt
```

### 3. Configura las Variables de Entorno

El proyecto utiliza un archivo `.env` para gestionar las variables de entorno, como las credenciales de la base de datos y las claves secretas.

1. Pedi el archivo .env (contiene las credenciales del supabase)
2. Tiralo en la carpeta principal con el nombre credenciales.env
3. El archivo `.env` ya contiene las claves necesarias para ejecutar el proyecto en el entorno de desarrollo proporcionado. No necesitas modificarlo para empezar.

**Nota de Seguridad Importante:** El archivo `.env` contiene información sensible. Está excluido del control de versiones (en `.gitignore`) para prevenir que se suba accidentalmente a un repositorio. **Nunca compartas ni publiques el contenido de este archivo.**

### 4. Ejecuta la Aplicación

Una vez que hayas completado los pasos anteriores, puedes iniciar el servidor de desarrollo de Flask.

```bash
python main.py
```

Después de ejecutar el comando, verás un mensaje en la terminal indicando que el servidor se está ejecutando, generalmente en `http://127.0.0.1:5000`.

¡Abre esa dirección en tu navegador y listo! Ya puedes interactuar con la aplicación.
