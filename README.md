# Medical Insurance Web App - Django Backend

A fully functional Django backend for the Medical Insurance Web Application with OTP-based authentication using SMTP.

## Features

### Authentication
- ✅ OTP-based email authentication (SMTP)
- ✅ Session management
- ✅ User profile management
- ✅ Secure login/logout

### Insurance Management
- ✅ Multi-language support (English, Malayalam, Arabic, Hindi)
- ✅ Employee and Dependent applications
- ✅ Emirates ID document upload and OCR processing
- ✅ Automated product recommendations based on salary and location
- ✅ Policy creation and management
- ✅ One policy per Emirates ID rule enforcement

### Chat System
- ✅ AI Assistant chat history storage
- ✅ Session-based conversations
- ✅ Insurance flow chat tracking

## Tech Stack

- **Backend**: Django 5.2.10
- **API**: Django REST Framework
- **Database**: SQLite3 (development) / PostgreSQL (production)
- **Email**: SMTP (Gmail/Custom)
- **Frontend**: Vanilla HTML/CSS/JS with TailwindCSS

## Installation

### Prerequisites
- Python 3.8 or higher
- pip package manager

### Setup Instructions

1. **Install Dependencies**
```bash
pip install django djangorestframework django-cors-headers pillow python-dotenv
```

2. **Configure Environment Variables**

Copy `.env.example` to `.env` and update with your settings:

```bash
cp .env.example .env
```

Edit `.env`:
```env
# For Gmail SMTP
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password-here
```

**Important**: For Gmail, you need to create an "App Password":
1. Go to Google Account Settings
2. Security → 2-Step Verification → App passwords
3. Generate a new app password for "Mail"
4. Use this password in `EMAIL_HOST_PASSWORD`

3. **Run Migrations**
```bash
python manage.py makemigrations
python manage.py migrate
```

4. **Create Superuser (Admin)**
```bash
python manage.py createsuperuser
```

5. **Run Development Server**
```bash
python manage.py runserver
```

The application will be available at: `http://127.0.0.1:8000`

## API Endpoints

### Authentication (`/api/auth/`)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/api/auth/send-otp/` | Send OTP to email | No |
| POST | `/api/auth/verify-otp/` | Verify OTP and login | No |
| POST | `/api/auth/logout/` | Logout user | Yes |
| GET | `/api/auth/me/` | Get current user | Yes |
| GET | `/api/auth/check/` | Check auth status | No |

### Insurance (`/api/insurance/`)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/api/insurance/applications/` | List applications | Yes |
| POST | `/api/insurance/applications/` | Create application | Yes |
| GET | `/api/insurance/applications/{id}/` | Get application | Yes |
| PUT/PATCH | `/api/insurance/applications/{id}/` | Update application | Yes |
| GET | `/api/insurance/applications/active/` | Get active application | Yes |
| POST | `/api/insurance/process-ocr/` | Process Emirates ID OCR | Yes |
| POST | `/api/insurance/recommendations/` | Get product recommendations | Yes |
| POST | `/api/insurance/create-policy/` | Create insurance policy | Yes |
| GET | `/api/insurance/policies/` | List user policies | Yes |
| GET | `/api/insurance/policies/active/` | Get active policies | Yes |
| GET/POST | `/api/insurance/chat/` | Chat message management | Yes |

## API Usage Examples

### 1. Send OTP
```javascript
fetch('http://127.0.0.1:8000/api/auth/send-otp/', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
    },
    body: JSON.stringify({
        email: 'user@example.com'
    })
})
```

### 2. Verify OTP
```javascript
fetch('http://127.0.0.1:8000/api/auth/verify-otp/', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify({
        email: 'user@example.com',
        otp_code: '1234'
    })
})
```

### 3. Create Insurance Application
```javascript
fetch('http://127.0.0.1:8000/api/insurance/applications/', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify({
        language: 'en',
        application_type: 'Employee',
        salary_range: '>5000',
        emirates_id: '784-2020-1234567-1',
        full_name: 'John Doe',
        expiry_date: '2026-12-31',
        nationality: 'India',
        gender: 'Male',
        issuing_place: 'Dubai',
        mobile_number: '+971501234567'
    })
})
```

### 4. Upload Emirates ID (OCR)
```javascript
const formData = new FormData();
formData.append('document', fileInput.files[0]);
formData.append('application_id', '1');

fetch('http://127.0.0.1:8000/api/insurance/process-ocr/', {
    method: 'POST',
    credentials: 'include',
    body: formData
})
```

### 5. Get Product Recommendations
```javascript
fetch('http://127.0.0.1:8000/api/insurance/recommendations/', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify({
        salary_range: '>5000',
        issuing_place: 'Dubai'
    })
})
```

## Database Models

### Authentication Models
- **User** - Django default user model
- **UserProfile** - Extended user profile
- **OTP** - OTP verification records

### Insurance Models
- **InsuranceApplication** - Insurance application records
- **InsurancePolicy** - Active insurance policies
- **ChatMessage** - Chat history for AI assistant

## Product Logic

### Dubai
- **Salary < 4000 AED**: DHA Basic (LSB) - 864.00 AED
- **Salary 4000-5000 or >5000 AED**: 
  - DHA Basic (LSB) - 864.00 AED
  - DHA Basic (NLSB) - 1893.00 AED

### Abu Dhabi
- **Salary < 5000 AED**: No products available
- **Salary > 5000 AED**: DHA Basic (NLSB) - 1893.00 AED

### Other Emirates
- Default: DHA Basic (LSB) - 864.00 AED

## Business Rules

1. ✅ Only one active medical insurance policy per Emirates ID
2. ✅ Multiple Emirates IDs can be linked to one email account
3. ✅ Emirates ID must be valid (not expired)
4. ✅ Insurance flow must be completed before creating policy
5. ✅ Chat history for medical insurance is only stored when process is completed

## Admin Panel

Access the Django admin panel at: `http://127.0.0.1:8000/admin/`

Features:
- User management
- OTP verification logs
- Insurance application tracking
- Policy management
- Chat history review

## Development vs Production

### Development (Current Setup)
- Uses console email backend (prints to terminal)
- SQLite database
- DEBUG=True
- CORS allowed for localhost

### Production Setup
1. Change `EMAIL_BACKEND` to SMTP in `.env`
2. Configure production database (PostgreSQL recommended)
3. Set `DEBUG=False`
4. Configure `ALLOWED_HOSTS`
5. Set up proper static file serving
6. Use environment secrets management
7. Enable HTTPS
8. Configure CORS for production domain

## Security Considerations

- ✅ OTP expiry (10 minutes default)
- ✅ Session-based authentication
- ✅ CSRF protection
- ✅ CORS configuration
- ✅ Email validation
- ✅ File upload validation (PDF, JPG, PNG only)
- ⚠️ Remember to change SECRET_KEY in production
- ⚠️ Use HTTPS in production
- ⚠️ Implement rate limiting for OTP requests

## Troubleshooting

### Emails not sending
- Check SMTP credentials in `.env`
- Verify Gmail app password is correct
- Check firewall/antivirus settings
- For development, use console backend

### CORS errors
- Ensure `credentials: 'include'` is set in fetch requests
- Check CORS_ALLOWED_ORIGINS in settings.py
- Verify frontend is running on allowed origin

### Database errors
- Run migrations: `python manage.py migrate`
- Check if migrations are created: `python manage.py makemigrations`

## Next Steps

1. **Integrate Real OCR Service**
   - Google Cloud Vision API
   - AWS Textract
   - Azure Computer Vision

2. **Add Payment Gateway**
   - Stripe
   - PayPal
   - UAE payment providers

3. **Enhance AI Assistant**
   - Integrate OpenAI GPT
   - Add context-aware responses
   - Multi-language support

4. **Add Notifications**
   - Email notifications
   - SMS notifications
   - Push notifications

5. **Testing**
   - Write unit tests
   - Integration tests
   - API endpoint tests

## License

MIT License

## Support

For issues or questions, contact: support@example.com
