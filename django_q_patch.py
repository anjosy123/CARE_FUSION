import os
import fileinput
import sys
from distutils.sysconfig import get_python_lib

def patch_django_q():
    # Get the correct site-packages path
    site_packages = get_python_lib()
    
    # Construct the correct path to django_q's core_signing.py
    django_q_path = os.path.join(site_packages, 'django_q', 'core_signing.py')
    
    print(f"Attempting to patch file at: {django_q_path}")
    
    if not os.path.exists(django_q_path):
        print(f"Error: File not found at {django_q_path}")
        return
    
    try:
        # The line to replace
        old_line = 'from django.utils import baseconv\n'
        new_line = 'from baseconv import base62 as baseconv\n'
        
        # Create backup
        backup_path = django_q_path + '.bak'
        if os.path.exists(backup_path):
            os.remove(backup_path)
            
        # Perform the replacement
        with fileinput.FileInput(django_q_path, inplace=True, backup='.bak') as file:
            for line in file:
                print(line.replace(old_line, new_line), end='')
                
        print("Successfully patched django_q core_signing.py")
        
    except Exception as e:
        print(f"Error during patching: {str(e)}")
        if os.path.exists(backup_path):
            os.replace(backup_path, django_q_path)
            print("Restored original file from backup")

if __name__ == "__main__":
    patch_django_q() 