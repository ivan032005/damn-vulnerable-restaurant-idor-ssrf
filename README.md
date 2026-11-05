# Proyecto Final — Seguridad de Software (UCC)
## Hack & Fix de Damn Vulnerable RESTaurant (DVRestaurant)

**Autor:** Ivan Orozco Fontalvo
**Aplicación objetivo:** [Damn Vulnerable RESTaurant API Game](https://github.com/theowni/Damn-Vulnerable-RESTaurant-API-Game) (FastAPI + PostgreSQL), ejecutada localmente vía Docker.
**Vulnerabilidades trabajadas:**
1. **IDOR / Broken Object Level Authorization** — `PUT /profile` (Level 2)
2. **SSRF (Server-Side Request Forgery)**, encadenada con una **escalación de privilegios** — `PUT /menu/{id}` + `PUT /users/update_role` (Level 4, prerequisito Level 3)

---

## 1. Estructura del repositorio

```
.
├── app/                                  # Código fuente de DVRestaurant (fork)
│   ├── apis/
│   │   ├── auth/services/
│   │   │   └── update_profile_service.py # Vulnerabilidad 1 (IDOR) — antes y después
│   │   ├── menu/
│   │   │   └── utils.py                  # Vulnerabilidad 2 (SSRF) — antes y después
│   │   ├── users/services/
│   │   │   └── update_user_role_service.py # Endpoint usado para la escalación de rol
│   │   └── admin/                        # Endpoint objetivo de la SSRF (/admin/reset-chef-password)
│   ├── db/models.py                      # Modelos y enum UserRole
│   └── ...
├── docker-compose.yml
├── start_app.sh / stop_app.sh
├── postman/
│   └── DVRestaurant.postman_collection.json   # Colección usada para los PoC (opcional, exportar desde Postman)
├── evidencias/
│   ├── 01_idor/                          # Capturas: código vulnerable, ataque, código corregido, validación
│   ├── 02_ssrf/                          # Capturas: código vulnerable, ataque, decodificación, código corregido, validación
│   └── 03_lecciones_aprendidas/          # Capturas de troubleshooting (errores 401/422/500, ImportError)
├── informe_ejecutivo.pdf                 # Exportado desde el documento vivo (Claude Docs)
└── README.md                             # Este archivo
```

> Nota: el código fuente completo de DVRestaurant no se reproduce en este README; vive en `app/` como fork del repositorio original, con los dos archivos de la tabla de abajo modificados.

## 2. Cómo levantar el entorno

Requisitos: Docker y Docker Compose.

```bash
git clone <url-de-tu-fork>
cd Damn-Vulnerable-RESTaurant-API-Game-main
./start_app.sh -d          # levanta la API en http://localhost:8091
docker compose logs -f web # logs en vivo (útil para diagnóstico)
./stop_app.sh               # apagar
```

La documentación interactiva (Swagger) queda disponible en `http://localhost:8091/docs`.

## 3. Resumen de las vulnerabilidades

| # | Vulnerabilidad | Endpoint | Archivo | Categoría OWASP |
|---|---|---|---|---|
| 1 | IDOR / Broken Object Level Authorization | `PUT /profile` | `app/apis/auth/services/update_profile_service.py` | API1:2023 (≈ A01:2021) |
| 2 | SSRF, encadenada con escalación de privilegios | `PUT /menu/{id}` + `PUT /users/update_role` | `app/apis/menu/utils.py` | API7:2023 (≈ A10:2021) |

Detalle completo (causa raíz, impacto, riesgo, mitigación aplicada, validación antes/después y reflexión ética) en `informe_ejecutivo.pdf`.

## 4. Cómo reproducir los PoC

### 4.1 IDOR — `PUT /profile`

1. Registrar dos usuarios: `atacante` y `victima` (`POST /register`).
2. Autenticarse como `atacante` (`POST /token`) y guardar el token.
3. Con ese token, enviar `PUT /profile` con `"username": "victima"` y datos arbitrarios → la API modifica el perfil de `victima` sin verificar que coincida con el usuario autenticado.
4. **Corrección:** el backend ahora usa `current_user.username` (identidad del token) en vez del `username` del body.
5. Re-ejecutar el mismo ataque tras la corrección: solo modifica el propio perfil del atacante.

### 4.2 SSRF — `PUT /menu/{id}` (requiere escalar a rol `Employee`)

1. Con el token de `atacante`, enviar `PUT /users/update_role` con `{"role": "Employee"}` (valor del enum sensible a mayúsculas).
2. Con el rol `Employee`, enviar `PUT /menu/1` con `"image_url": "http://127.0.0.1:8091/admin/reset-chef-password"`.
3. La respuesta trae `image_base64` con el contenido de ese endpoint interno codificado en Base64; decodificar con `atob(...)` en la consola del navegador revela la contraseña del Chef.
4. **Corrección:** `_is_safe_url()` resuelve el DNS y bloquea loopback/privadas/link-local/reservadas/multicast antes de hacer la petición saliente; además se deshabilitan redirecciones y se valida el `Content-Type` de la respuesta.
5. Re-ejecutar el ataque tras la corrección → `400 Bad Request`. Validar que una URL de imagen legítima (sin redirección) sigue funcionando (`200 OK`).

## 5. Alcance ético

Todas las pruebas se ejecutaron **exclusivamente contra una instancia local** (`localhost:8091`) de la aplicación, con datos de prueba (`atacante`, `victima`) creados para el ejercicio. No se intervino ningún sistema de terceros ni se expuso el entorno a internet. Detalle de la justificación ética en la sección 7 de `informe_ejecutivo.pdf`.


