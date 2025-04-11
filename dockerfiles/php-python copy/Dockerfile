# Use official PHP with Apache
FROM php:8.2-apache

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
    && docker-php-ext-install mbstring zip pdo pdo_mysql mysqli

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
    typing

# Set environment variable so the system uses Python from the virtual environment
ENV PATH="/opt/venv/bin:$PATH"

# Enable Apache mod_rewrite
RUN a2enmod rewrite

# Set working directory for Apache
WORKDIR /var/www/html

# Expose Apache port
EXPOSE 80

# Start Apache
CMD ["apache2-foreground"]
