FROM php:8.2-apache
COPY . /var/www/html/
RUN a2enmod rewrite
EX不可 EXPOSE 80
