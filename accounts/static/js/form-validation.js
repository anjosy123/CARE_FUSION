document.addEventListener('DOMContentLoaded', function() {
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        const inputs = form.querySelectorAll('input');
        inputs.forEach(input => {
            input.addEventListener('input', validateInput);
            input.addEventListener('blur', validateInput);
        });
    });
});

function validateInput(event) {
    const input = event.target;
    const value = input.value.trim();
    let isValid = true;
    let errorMessage = '';

    switch (input.id) {
        case 'username':
            if (value.length < 3) {
                isValid = false;
                errorMessage = 'Username must be at least 3 characters long';
            }
            break;
        case 'email':
            if (!isValidEmail(value)) {
                isValid = false;
                errorMessage = 'Please enter a valid email address';
            }
            break;
        case 'passw1':
        case 'pass1':
            if (value.length < 8) {
                isValid = false;
                errorMessage = 'Password must be at least 8 characters long';
            }
            break;
        case 'passw2':
            const password = document.getElementById('passw1').value;
            if (value !== password) {
                isValid = false;
                errorMessage = 'Passwords do not match';
            }
            break;
    }

    setInputValidationState(input, isValid, errorMessage);
}

function isValidEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

function setInputValidationState(input, isValid, errorMessage) {
    const errorElement = input.nextElementSibling;
    if (!errorElement || !errorElement.classList.contains('error-message')) {
        const newErrorElement = document.createElement('div');
        newErrorElement.classList.add('error-message');
        input.parentNode.insertBefore(newErrorElement, input.nextSibling);
    }

    if (!isValid) {
        input.classList.add('is-invalid');
        input.classList.remove('is-valid');
        errorElement.textContent = errorMessage;
        errorElement.style.display = 'block';
    } else {
        input.classList.remove('is-invalid');
        input.classList.add('is-valid');
        errorElement.textContent = '';
        errorElement.style.display = 'none';
    }
}
