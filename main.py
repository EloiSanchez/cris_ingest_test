import json
from pathlib import Path
from typing import DefaultDict, NamedTuple
import requests
from tempfile import TemporaryDirectory
from xml.etree import ElementTree as ET

import xmltodict
import duckdb

# Useful links:
# - Spec definition: https://www.openarchives.org/OAI/openarchivesprotocol.html


class OpenAireSet(NamedTuple):
    short_name: str
    openaire_name: str
    xml_xpath: str
    extract_key: str


class CRIS:

    def __init__(self, name: str, base_url: str) -> None:
        self.base_url = base_url
        self.name = name

    def harvest_set(self, openaire_set: OpenAireSet, max_requests: int = 5):

        # Initialize return variables
        fetch_success = True
        target_table = f"cris_{self.name}__{openaire_set.short_name}"
        temp_dir = TemporaryDirectory(delete=False)

        data_dir = Path(f"{temp_dir.name}")

        # Params on first fetch MUST include metadataPrefix
        params = {
            "verb": "ListRecords",
            # "verb": "ListSets",
            "metadataPrefix": "oai_cerif_openaire",
            "set": openaire_set.openaire_name,
        }

        print(f"Starting fetch for {self.name}:{openaire_set.short_name}")

        # Start main request loop
        num_requests = 0
        while num_requests < max_requests:

            num_requests += 1
            try:

                # Perform request
                response = requests.get(self.base_url, params=params)
                response.raise_for_status()

                # Parse required information
                root = ET.fromstring(response.text)
                parsed_data = [
                    xmltodict.parse(
                        ET.tostring(publication).decode(),
                        process_namespaces=True,
                        namespaces=DefaultDict(lambda: None),
                    )[openaire_set.extract_key]
                    for publication in root.findall(openaire_set.xml_xpath)
                ]

                # Save batch to temp dict
                with open(data_dir / f"{self.name}_{num_requests}.json", "w") as f:
                    json.dump(parsed_data, f)

                # OPTIONAL: Save raw xml and parsed json of first request for analysis
                if num_requests == 1:
                    results_dir = Path("results/")
                    responses_dir = results_dir / "responses" / self.name

                    responses_dir.mkdir(parents=True, exist_ok=True)
                    with open(
                        responses_dir / f"{openaire_set.short_name}.xml",
                        "w",
                    ) as f:
                        f.write(response.text)

                    parsed_dir = results_dir / "parsed" / self.name
                    parsed_dir.mkdir(parents=True, exist_ok=True)
                    with open(
                        parsed_dir / f"{openaire_set.short_name}.json",
                        "w",
                    ) as f:
                        json.dump(parsed_data, f, indent=2)
                # END OPTIONAL

            # For now, if exception, ignore and jump to next
            except Exception as e:
                print(
                    "Error found while processing "
                    f"{self.name}:{openaire_set.short_name} on request {num_requests}."
                    # f"\n{json.dumps(response_dict, indent=2)}"
                    f"\n{e}"
                )
                fetch_success = False
                break

            # Paginate if needed
            resumption_token = root.find(
                ".//{http://www.openarchives.org/OAI/2.0/}resumptionToken"
            )
            if resumption_token is None or resumption_token.text is None:
                break

            params = {"verb": "ListRecords", "resumptionToken": resumption_token.text}

        return target_table, temp_dir, fetch_success


def ingest_data(
    con: duckdb.DuckDBPyConnection,
    source_dir: TemporaryDirectory,
    target_table_name: str,
):
    con.sql("create schema if not exists sources")
    con.sql("use sources")
    con.sql(f"drop table if exists {target_table_name}")

    source_path = Path(source_dir.name)

    df = con.read_json(source_path / "*.json", ignore_errors=True)
    # if target_table_exists:
    #     res = df.insert_into(target_table_name)
    # else:
    df.to_table(target_table_name)
    source_dir.cleanup()


CRIS_REPOSITORIES = [
    CRIS(
        name="maastrichtuniversity",
        base_url="https://cris.maastrichtuniversity.nl/ws/oai",
    ),
    CRIS(
        name="uci",
        base_url="https://oamemtfp.uci.ru.nl/metis-oaipmh-endpoint/OAIHandler",
    ),
    CRIS(
        name="amsterdamumc",
        base_url="https://pure.amsterdamumc.nl/ws/oai",
    ),
    CRIS(
        name="eur",
        base_url="https://pure.eur.nl/ws/oai",
    ),
    CRIS(
        name="hva",
        base_url="https://pure.hva.nl/ws/oai",
    ),
    CRIS(
        name="rug",
        base_url="https://pure.rug.nl/ws/oai",
    ),
    CRIS(
        name="tudelft",
        base_url="https://pure.tudelft.nl/ws/oai",
    ),
    CRIS(
        name="tue",
        base_url="https://pure.tue.nl/ws/oai",
    ),
    CRIS(
        name="uva",
        base_url="https://pure.uva.nl/ws/oai",
    ),
    CRIS(
        name="uvt",
        base_url="https://pure.uvt.nl/ws/oai",
    ),
    CRIS(
        name="uu",
        base_url="https://research-portal.uu.nl/ws/oai",
    ),
    CRIS(
        name="ou",
        base_url="https://research.ou.nl/ws/oai",
    ),
    CRIS(
        name="vu",
        base_url="https://research.vu.nl/ws/oai",
    ),
    CRIS(
        name="vumc",
        base_url="https://research.vumc.nl/ws/oai",
    ),
    CRIS(
        name="utwente",
        base_url="https://ris.utwente.nl/ws/oai",
    ),
]

OPENAIRE_SETS = [
    OpenAireSet(
        short_name="publications",
        openaire_name="openaire_cris_publications",
        xml_xpath=".//{https://www.openaire.eu/cerif-profile/1.2/}Publication",
        extract_key="Publication",
    ),
    OpenAireSet(
        short_name="patents",
        openaire_name="openaire_cris_patents",
        xml_xpath=".//{https://www.openaire.eu/cerif-profile/1.2/}Patent",
        extract_key="Patent",
    ),
    OpenAireSet(
        short_name="persons",
        openaire_name="openaire_cris_persons",
        xml_xpath=".//{https://www.openaire.eu/cerif-profile/1.2/}Person",
        extract_key="Person",
    ),
    OpenAireSet(
        short_name="orgunits",
        openaire_name="openaire_cris_orgunits",
        xml_xpath=".//{https://www.openaire.eu/cerif-profile/1.2/}OrgUnit",
        extract_key="OrgUnit",
    ),
    OpenAireSet(
        short_name="events",
        openaire_name="openaire_cris_events",
        xml_xpath=".//{https://www.openaire.eu/cerif-profile/1.2/}Event",
        extract_key="Event",
    ),
    OpenAireSet(
        short_name="equipments",
        openaire_name="openaire_cris_equipments",
        xml_xpath=".//{https://www.openaire.eu/cerif-profile/1.2/}Equipment",
        extract_key="Equipment",
    ),
    OpenAireSet(
        short_name="products",
        openaire_name="openaire_cris_products",
        xml_xpath=".//{https://www.openaire.eu/cerif-profile/1.2/}Product",
        extract_key="Product",
    ),
]
MAX_REQUESTS = 2


def main():

    Path("data/").mkdir(exist_ok=True)
    con = duckdb.connect("ducklake:data/broccoli.ducklake")

    # for repo in CRIS_REPOSITORIES:
    # target_table, temp_dir, fetch_success = CRIS_REPOSITORIES[0].harvest_set(
    #     OPENAIRE_SETS[0], max_requests=1
    # )

    # if fetch_success:
    #     ingest_data(con, temp_dir, target_table)
    # else:
    #     print("Error on fetch")

    for cris_repository in CRIS_REPOSITORIES:
        for openaire_set in OPENAIRE_SETS:
            target_table, temp_dir, fetch_success = cris_repository.harvest_set(
                openaire_set, max_requests=5
            )
            if fetch_success:
                ingest_data(con, temp_dir, target_table)


if __name__ == "__main__":
    main()
