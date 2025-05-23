# Use official PHP with Apache
FROM php:8.2-apache

# Add image labels
LABEL org.opencontainers.image.title="php82-python" \
      org.opencontainers.image.version="latest" \
      maintainer="puneet1984"

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libonig-dev \
    libzip-dev \
    curl \
    unzip \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    libssl-dev \
    git \
    wget \
    supervisor \
    cron \
    && docker-php-ext-install mbstring zip pdo pdo_mysql mysqli

# Install Composer
RUN curl -sS https://getcomposer.org/installer | php -- --install-dir=/usr/local/bin --filename=composer

# Create composer directory and install PHPMailer
WORKDIR /var/www
RUN composer require phpmailer/phpmailer

# Set working directory back to Apache default
WORKDIR /var/www/html

# Create and activate Python virtual environment
RUN python3 -m venv /opt/venv

# Install required Python packages inside the virtual environment
RUN /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir \
    flask \
    websockets \
    asyncio \
    asterisk-ami \
    pymysql \
    requests \
    beautifulsoup4 \
    typing \
    watchdog \
    ftputil \
    pytz \
    python-dotenv \
    werkzeug

# Set environment variable so the system uses Python from the virtual environment
ENV PATH="/opt/venv/bin:$PATH"

# Enable Apache mod_rewrite
RUN a2enmod rewrite

# Copy and enable Apache configuration
COPY vhost.conf /etc/apache2/sites-available/000-default.conf
RUN a2ensite 000-default.conf

# Create services and logs directories
RUN mkdir -p /opt/services /var/log/app && \
    chmod -R 777 /var/log/app

# Setup crontab
RUN echo "*/3 9-22 * * * /opt/venv/bin/python /opt/services/patient_alert_service.py >> /var/log/app/patient_alert.log 2>&1" > /etc/cron.d/app-cron && \
    echo "0 10 * * * /opt/venv/bin/python /opt/services/stock_alert_service.py >> /var/log/app/stock_alert.log 2>&1" >> /etc/cron.d/app-cron && \
    chmod 0644 /etc/cron.d/app-cron && \
    crontab /etc/cron.d/app-cron

# Copy Python service files and env file
COPY *.py .env /opt/services/
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Set permissions for Python files
RUN chmod +x /opt/services/*.py && \
    chown -R www-data:www-data /opt/services

# Set working directory for Apache
WORKDIR /var/www/html

# Expose ports
EXPOSE 80 5000 5001 5002

# Update CMD to run both cron and supervisor
CMD ["sh", "-c", "service cron start && /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf"]
