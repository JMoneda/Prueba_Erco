#!/usr/bin/env python3
"""
Script para generar un SECRET_KEY seguro
"""
import secrets
import string

def generate_secret_key(length=32):
    """Genera una clave secreta segura"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

if __name__ == "__main__":
    print("🔐 Generador de SECRET_KEY para ERCO Energy Monitor")
    print("=" * 50)
    
    # Generar diferentes tipos de claves
    simple_key = secrets.token_urlsafe(32)
    complex_key = generate_secret_key(48)
    hex_key = secrets.token_hex(32)
    
    print("\n1. Clave URL-safe (recomendada para JWT):")
    print(f"   {simple_key}")
    
    print("\n2. Clave compleja (con caracteres especiales):")
    print(f"   {complex_key}")
    
    print("\n3. Clave hexadecimal:")
    print(f"   {hex_key}")
    
    print("\n📋 Copia una de estas claves y pégala en tu archivo .env")
    print("   como valor de SECRET_KEY")