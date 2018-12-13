all: down build up

build:
	docker build . -t memcache-server
	docker build -f frontend/Dockerfile -t memcache-frontend frontend

up:
	docker-compose up

down:
	docker-compose down

status:
	docker-compose ps

local:
	pipenv run watchmedo auto-restart -d . -p "*.py" -DR -- python main.py

test:
	pipenv run pytest --cov=.
