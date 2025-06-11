#!/usr/bin/env python3

import os
import subprocess
import getpass
import re
import tempfile

def run_command(command):
    """Run a shell command and return its output."""
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {command}")
        print(f"Error: {e.stderr}")
        raise

def generate_private_key(username, encrypted=True, passphrase=None):
    """Generate private key file with or without encryption."""
    key_file = f"{username}_rsa_key.p8"
    
    if encrypted:
        print("\nGenerating encrypted private key...")
        # Create a temporary file for the passphrase
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp:
            temp.write(passphrase)
            temp_path = temp.name
        
        try:
            # Generate the key and encrypt it using the passphrase file
            command = f"openssl genrsa 2048 | openssl pkcs8 -topk8 -v2 des3 -inform PEM -out {key_file} -passout file:{temp_path}"
            run_command(command)
            print(f"✅ Encrypted private key generated: {key_file}")
        finally:
            # Clean up the temporary file
            os.unlink(temp_path)
    else:
        print("\nGenerating unencrypted private key...")
        command = f"openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out {key_file} -nocrypt"
        run_command(command)
        print(f"✅ Unencrypted private key generated: {key_file}")

def generate_public_key(username, encrypted=False, passphrase=None):
    """Generate public key from private key."""
    private_key = f"{username}_rsa_key.p8"
    public_key = f"{username}_rsa_key.pub"
    
    print("\nGenerating public key...")
    if encrypted:
        # Create a temporary file for the passphrase
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp:
            temp.write(passphrase)
            temp_path = temp.name
        
        try:
            command = f"openssl rsa -in {private_key} -passin file:{temp_path} -pubout -out {public_key}"
            run_command(command)
        finally:
            # Clean up the temporary file
            os.unlink(temp_path)
    else:
        command = f"openssl rsa -in {private_key} -pubout -out {public_key}"
        run_command(command)
    
    print(f"✅ Public key generated: {public_key}")

def process_private_key(username):
    """Process private key file to replace newlines."""
    input_file = f"{username}_rsa_key.p8"
    output_file = f"{username}_rsa_key_processed.p8"
    
    print("\nProcessing private key file...")
    with open(input_file, 'r') as f:
        content = f.read()
    
    # Replace newlines with \n
    processed_content = content.replace('\n', '\\n')
    
    with open(output_file, 'w') as f:
        f.write(processed_content)
    
    print(f"✅ Processed private key saved to: {output_file}")

def print_snowflake_command(username):
    """Print the Snowflake ALTER USER command with the public key."""
    public_key_file = f"{username}_rsa_key.pub"
    
    print("\nSnowflake ALTER USER Command:")
    print("=============================")
    
    with open(public_key_file, 'r') as f:
        content = f.read()
    
    # Remove header and footer lines and join the key content
    lines = content.strip().split('\n')
    if len(lines) > 2:
        key_content = ''.join(lines[1:-1])
        # Format the ALTER USER command
        alter_command = f"""-- Run this command in Snowflake to set up key pair authentication
ALTER USER {username} SET RSA_PUBLIC_KEY='{key_content}';

-- Verify the key was set correctly
DESC USER {username};"""
        print(alter_command)
    else:
        print("Error: Public key file format is not as expected")

def main():
    print("Snowflake Key Pair Generator")
    print("============================")
    
    # Step 1: Get username
    username = input("\nEnter Snowflake username: ").strip()
    
    # Step 2: Choose encryption option
    while True:
        print("\nChoose key encryption option:")
        print("1. Encrypted (recommended)")
        print("2. Unencrypted")
        choice = input("Enter choice (1 or 2): ").strip()
        
        if choice in ['1', '2']:
            break
        print("Invalid choice. Please enter 1 or 2.")
    
    encrypted = choice == '1'
    
    # Step 2a: Get passphrase if encrypted
    passphrase = None
    if encrypted:
        print("\nYou will be prompted for a passphrase to encrypt the private key.")
        print("IMPORTANT: Save this passphrase securely - you will need it for Snowflake configuration.")
        passphrase = getpass.getpass("Enter passphrase: ")
        if not passphrase:
            print("Error: Passphrase cannot be empty")
            return
    
    # Generate private key
    generate_private_key(username, encrypted, passphrase)
    
    # Generate public key
    generate_public_key(username, encrypted, passphrase)
    
    # Process private key
    process_private_key(username)
    
    # Print Snowflake command
    print_snowflake_command(username)
    
    print("\n✅ Key pair generation complete!")
    if encrypted:
        print("\nIMPORTANT: Save your passphrase securely!")
        print(f"Passphrase: {passphrase}")

if __name__ == "__main__":
    main() 