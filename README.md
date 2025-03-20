# One Request to Rule Them All!

The One Request CTF event was hosted from February 27th to March 2nd, 2025 by APIsec University. The application 
utilized in the event is available in this repository, with minimal modifications, for educational purposes.

For example, the challenge descriptions and flag validation functionality were added directly to the application for 
public release.

## Running the Application via Docker

The easiest way to run the application is via Docker and Docker Compose. Run the following commands to start the application on your system:

```shell
git clone https://github.com/apisec-university/one-request.git
cd one-request
docker compose up -d 
```

The application should now be available on http://localhost:8000. 

To stop the application, run `docker compose down` from the repo directory.

## Running the Application Locally via Poetry

To run the application locally, you will need to have Python3 installed on your system. Python 3.10+ is recommended.

Run the following commands to start the application:

```shell
poetry install
poetry shell
poetry run dev
```

The application should now be available on http://localhost:8000.

## Solving the Application

Numerous write-ups are available online from the original event. 

Want yours included here? Submit a PR or message us in Discord!

To verify application can be solved using the included `solve.py` script, run the following commands:

```shell
poetry install
poetry run solve
```

## Application Data 

Data is stored in the SQLite database at `data/one_request.sqlite3`.

To reset the application to a fresh start, checkout the database file to it's original state.

```shell
git checkout -- data/one_request.sqlite3
```

#### Generating New Data

If you wish to generate new data for the application, the `gen_data.py` script can be used.

```shell
rm data/one_request.sqlite3
poetry install
poetry shell
alembic upgrade head
python scripts/gen_data.py
```
