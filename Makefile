all: down image up

image:
	docker build . -t memcache-server

up:
	docker-compose up

down:
	docker-compose down

status:
	docker-compose ps

local:
	pipenv run watchmedo auto-restart -d . -p "*.py" -DR -- python main.py
