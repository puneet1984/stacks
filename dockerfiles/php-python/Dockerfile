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

# Create services and logs directories
RUN mkdir -p /opt/services && \
    mkdir -p ~/logs && \
    chmod -R 777 ~/logs

# Copy Python service files
COPY *.py /opt/services/

# Set execute permissions
RUN chmod +x /opt/services/*.py

# Copy supervisor configuration
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Create log directory and set permissions
RUN mkdir -p /var/log/supervisor && \
    touch /var/log/supervisor/supervisord.log && \
    chmod -R 777 /var/log

# Set working directory for Apache
WORKDIR /var/www/html

# Expose ports
EXPOSE 80 5000 5001 5002

# Change CMD to use supervisor
CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf"]
