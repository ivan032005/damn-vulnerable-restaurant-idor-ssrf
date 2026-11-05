import base64
import ipaddress
import socket
from urllib.parse import urlparse

import requests
from apis.menu import schemas
from db.models import MenuItem, OrderItem
from fastapi import HTTPException

# Solo se permiten estos esquemas para descargar imágenes
ALLOWED_SCHEMES = {"http", "https"}


def _is_safe_url(image_url: str) -> bool:
    """
    Valida que la URL no apunte a direcciones internas/privadas,
    evitando que el servidor sea usado para SSRF.
    """
    parsed = urlparse(image_url)

    if parsed.scheme not in ALLOWED_SCHEMES:
        return False
    if not parsed.hostname:
        return False

    try:
        resolved_ip = socket.gethostbyname(parsed.hostname)
        ip_obj = ipaddress.ip_address(resolved_ip)
    except (socket.gaierror, ValueError):
        return False

    if (
        ip_obj.is_loopback
        or ip_obj.is_private
        or ip_obj.is_link_local
        or ip_obj.is_reserved
        or ip_obj.is_multicast
    ):
        return False

    return True


def _image_url_to_base64(image_url: str):
    if not _is_safe_url(image_url):
        raise HTTPException(
            status_code=400,
            detail="La URL de la imagen no es válida o apunta a una dirección no permitida.",
        )

    response = requests.get(
        image_url,
        stream=True,
        timeout=5,
        allow_redirects=False,
    )

    content_type = response.headers.get("Content-Type", "")
    if not content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail="La URL proporcionada no apunta a una imagen válida.",
        )

    encoded_image = base64.b64encode(response.content).decode()
    return encoded_image


def create_menu_item(
    db,
    menu_item: schemas.MenuItemCreate,
):
    menu_item_dict = menu_item.dict()
    image_url = menu_item_dict.pop("image_url", None)
    db_item = MenuItem(**menu_item_dict)

    if image_url:
        db_item.image_base64 = _image_url_to_base64(image_url)

    db.add(db_item)
    db.commit()
    db.refresh(db_item)

    return db_item


def update_menu_item(
    db,
    item_id: int,
    menu_item: schemas.MenuItemCreate,
):
    db_item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
    if db_item is None:
        raise HTTPException(status_code=404, detail="Menu item not found")

    menu_item_dict = menu_item.dict()
    image_url = menu_item_dict.pop("image_url", None)

    for key, value in menu_item_dict.items():
        setattr(db_item, key, value)

    if image_url:
        db_item.image_base64 = _image_url_to_base64(image_url)

    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


def delete_menu_item(db, item_id: int):
    existing_order_item = (
        db.query(OrderItem).filter(OrderItem.menu_item_id == item_id).first()
    )
    if existing_order_item is not None:
        raise HTTPException(
            status_code=409,
            detail="You can not delete this menu item, it is associated with existing orders.",
        )

    db_item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
    if db_item is None:
        raise HTTPException(status_code=404, detail="Menu item not found")

    db.delete(db_item)
    db.commit()