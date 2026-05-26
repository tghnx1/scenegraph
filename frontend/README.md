# Read this first!

Steps from my side:
1. get the latest scenegraph_dump.sql from Maksim
2. pull this branch
3. `make upd` --> create & start containers
4. `docker compose exec -T db sh -lc 'PGPASSWORD="$POSTGRES_PASSWORD" psql -U "$POSTGRES_USER" -d postgres -c "CREATE ROLE postgres WITH SUPERUSER CREATEDB CREATEROLE LOGIN;"'` --> all one line, create role
5.  `RESET_DB=1 make import-dump DUMP=./backend/data/scenegraph_dump.sql` --> dont have to press 'y' to proceed
6. now containers are exited because the DB has changed, so `make upd` again.
7. open in browser `http://localhost:8080`