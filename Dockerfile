FROM php:8.2-apache
# Копируем всё содержимое в корень веб-сервера
COPY . /var/www/html/
# Гарантируем, что index.php находится на месте
RUN ls -l /var/www/html/
EXPOSE 80
