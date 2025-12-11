"""seed_geo_filter_data

Revision ID: b4dd0d1d2441
Revises: af8a8b3c33d5
Create Date: 2025-12-10 02:42:00.000000

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import String, column, table


# revision identifiers, used by Alembic.
revision: str = "b4dd0d1d2441"
down_revision: Union[str, None] = "af8a8b3c33d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


geo_filter_table = table(
    "geo_filter_data",
    column("division_id", String(36)),
    column("division_name_en", String(255)),
    column("country_code", String(10)),
)

DIVISIONS = [
    {"division_id": "7ac2bcfb-15f5-47cf-9eee-b12672d0d304", "division_name_en": "Abha"},
    {"division_id": "fe85390b-911e-42ee-a8d9-d63cd76bc4bc", "division_name_en": "Abqaiq Governorate"},
    {"division_id": "718df86a-7ce1-4e74-b915-8c49e37a0e89", "division_name_en": "Abu `Arish Governorate"},
    {"division_id": "1954c2ec-8c25-47d7-baa2-7c636dfcf7ef", "division_name_en": "Adam"},
    {"division_id": "4fe0bdd7-5dd1-461b-90c0-8149f0c1c182", "division_name_en": "Ad Darb"},
    {"division_id": "998d9cf1-6e49-4fc8-ad06-4d9e610230c7", "division_name_en": "Ad Dilam"},
    {"division_id": "6952417a-5f68-4957-b519-64741f85274d", "division_name_en": "Ad Diriyah"},
    {"division_id": "31f90679-d83c-4cc0-935e-54403bdb4085", "division_name_en": "Ad Duwadimi"},
    {"division_id": "59a3eafa-8607-47f7-9545-0a3276753e50", "division_name_en": "Afif"},
    {"division_id": "f12d3b05-a031-4e56-b90d-f9eafc2eb9a6", "division_name_en": "Ahad Al Masarihah"},
    {"division_id": "cff88574-4b34-4790-8119-2537741da19a", "division_name_en": "Ahad Rufaydah"},
    {"division_id": "6577549b-e02a-40de-a9e6-69d7071f2977", "division_name_en": "Al Aflaj"},
    {"division_id": "33053b08-f29c-4fce-b9f7-8681653bd871", "division_name_en": "Al Ahsa Governorate"},
    {"division_id": "d2cfb366-5d11-4b5f-bf78-c0bc420fc860", "division_name_en": "Al Aqiq"},
    {"division_id": "97d2eb7b-257a-4c4e-b4e6-fbcc17b66bb3", "division_name_en": "Al Ardhiyat"},
    {"division_id": "406b2402-9e7e-48c1-bfdc-f3b0a01e0404", "division_name_en": "Al Aridah"},
    {"division_id": "d9c1cf06-5d6c-420d-b66c-400d6c9fced5", "division_name_en": "Al Asyah"},
    {"division_id": "57b0069e-c1ce-461e-9660-d98fb7f7a670", "division_name_en": "Al Aydabi"},
    {"division_id": "7dcbd3c2-7a18-4b4a-8dec-505f60d748cc", "division_name_en": "Al-Bad'"},
    {"division_id": "5cd8b9a3-80ae-496c-a890-1d7feba55e78", "division_name_en": "Al Badai"},
    {"division_id": "020e16f5-2f97-49ec-adc1-81ae3c4f41e4", "division_name_en": "Al Bahah"},
    {"division_id": "847642b2-77a3-46a8-bfc0-93fc8fafd1ce", "division_name_en": "Al Birk"},
    {"division_id": "c8592576-bade-4563-830c-6ef08f358266", "division_name_en": "Al Bukayriyah"},
    {"division_id": "64e85331-cf73-451b-b416-0ab7fd6a0924", "division_name_en": "Al ddayer"},
    {"division_id": "cf7fd87d-5d71-4b34-9bc8-7c41fd1313eb", "division_name_en": "Al Ghat"},
    {"division_id": "4ee8c745-abcf-4d52-a231-973624e1023a", "division_name_en": "Al Ghazalah"},
    {"division_id": "25decf2b-32f8-426a-875e-d876a12cdb2f", "division_name_en": "Al Hait"},
    {"division_id": "2db53530-b397-4e81-a918-1b746ef5413f", "division_name_en": "Al Hajrah"},
    {"division_id": "16ca97f0-625b-40e3-86e8-fb2c4f9f1ffc", "division_name_en": "Al Hariq"},
    {"division_id": "100c5cd3-b7f8-41e0-ba91-18ada4aef442", "division_name_en": "Al Harjah"},
    {"division_id": "620ffc4f-6562-421d-87b5-ece6e6d2459f", "division_name_en": "Al Harth"},
    {"division_id": "20811828-101d-4bb7-aa67-cf125c4796fb", "division_name_en": "Al Hinakiyah"},
    {"division_id": "2c0c5f94-02e1-4af0-8fdc-978c6d5a508d", "division_name_en": "Al Is"},
    {"division_id": "6a169367-ee82-4391-b5a1-b353af7294eb", "division_name_en": "Al Jubayl Governorate"},
    {"division_id": "cd8ca153-b266-4f19-9a6e-6d72bac54dd4", "division_name_en": "Al Jumum"},
    {"division_id": "b89fed25-9582-4e10-bbe6-a6aae1f74375", "division_name_en": "Al Kamil"},
    {"division_id": "7429ad98-bdb2-4faa-9eec-8f4ac393f6e6", "division_name_en": "Al Khafji Governorate"},
    {"division_id": "adf6294a-180d-41d1-9747-2675994bcb91", "division_name_en": "Al Kharj"},
    {"division_id": "4fb8b660-dae4-4b0d-bd2f-b7fe19655406", "division_name_en": "Al Khurmah"},
    {"division_id": "77e040ab-9ed3-4656-b2af-06febdee6d76", "division_name_en": "Al Lith"},
    {"division_id": "35343237-72e3-4b33-bc4e-0b852ac8937b", "division_name_en": "Al Madinah Al Munawwarah"},
    {"division_id": "cc46e35d-b498-4f54-b737-4e98c1fd6334", "division_name_en": "Al Mahd"},
    {"division_id": "0fcc7c31-0cf0-42bd-8f5a-31a243bda47a", "division_name_en": "Al Majardah"},
    {"division_id": "1494a0a7-6b45-410e-8c55-6490cd0e00d2", "division_name_en": "Al Majmaah"},
    {"division_id": "943a9011-157a-41cd-8ed1-ede58248dcf3", "division_name_en": "Al Mandaq"},
    {"division_id": "99632774-3f2e-4661-be60-c926926da647", "division_name_en": "Al Midhnab"},
    {"division_id": "eb14689b-237c-40ae-9726-572b558d9501", "division_name_en": "Al Mukhwah"},
    {"division_id": "621d5057-8f9f-4d1e-8509-9881261b98f3", "division_name_en": "Al Muwayh"},
    {"division_id": "c1295175-07d6-4499-b2eb-999e6841760e", "division_name_en": "Al Muzahimiyah"},
    {"division_id": "e9800a8f-5792-4f3c-b065-7a87e38e57ea", "division_name_en": "Al Nuayriyah Governorate"},
    {"division_id": "196decc0-5613-49aa-9f69-f913ded3d070", "division_name_en": "Al Qara"},
    {"division_id": "61c14c41-b1eb-4ef7-be2b-54ebfb024bd2", "division_name_en": "Al Qunfudhah"},
    {"division_id": "5b1d47d9-0fad-4dcb-9b61-e41ea3f39662", "division_name_en": "Al Qurayyat"},
    {"division_id": "cc6365f3-2d59-42ca-ba95-13109f912af8", "division_name_en": "Al Quwayiyah"},
    {"division_id": "396fdfa5-66d4-43c8-92a6-ea5f964de4ca", "division_name_en": "Al Taif"},
    {"division_id": "99a8f27e-28c1-42a7-abfc-b6f287b16712", "division_name_en": "Al Udayd Governorate"},
    {"division_id": "5af07b2c-22ff-43ff-b9f9-3af6c559adc1", "division_name_en": "Al Ula"},
    {"division_id": "d4c554e9-aadb-4ada-8532-f5a6587a84ac", "division_name_en": "Al Uwayqilah"},
    {"division_id": "0309b97f-ad39-4d8e-a996-6a48210722e6", "division_name_en": "Al Wajh"},
    {"division_id": "61330ca1-a193-4b51-88f3-eadf20dbf216", "division_name_en": "An Nabhaniyah"},
    {"division_id": "22fd9809-add0-4986-ab47-5fcfd246d6cd", "division_name_en": "An Nimas"},
    {"division_id": "569811e9-8033-49a7-a444-f23e7d360f2a", "division_name_en": "Arar"},
    {"division_id": "1ec1577c-ec33-4874-905d-2c6bbf6b02bd", "division_name_en": "Ar Rass"},
    {"division_id": "6c810bdc-cfa0-4471-a556-4d3f8d7911de", "division_name_en": "Ar Rayn"},
    {"division_id": "eaa732d5-201e-4d75-a705-371add353f0d", "division_name_en": "Ar Rayth"},
    {"division_id": "390a9265-d882-4442-8c62-50792a814e97", "division_name_en": "Ash Shamli"},
    {"division_id": "41772ae6-046b-4e41-be72-e450ca9b94f4", "division_name_en": "Ash Shimasiyah"},
    {"division_id": "2dc681a2-203a-4f61-8069-a7dede89cbe1", "division_name_en": "Ash Shinan"},
    {"division_id": "2027dc1d-7756-468b-af3b-434f49d148a3", "division_name_en": "As Sulaymi"},
    {"division_id": "b16008c7-5967-459b-b5dd-1e93bafa41e6", "division_name_en": "As Sulayyil"},
    {"division_id": "3d30031f-ca47-41bb-aff4-a341ae16cfed", "division_name_en": "At Tuwal"},
    {"division_id": "734d09cd-88f9-4c59-bdf0-4b4c49af3bdb", "division_name_en": "Az Zulfi"},
    {"division_id": "86b74662-10a1-4053-81a0-2bc9e3f9eebf", "division_name_en": "Badr"},
    {"division_id": "8c4c100a-c5c5-409a-a6f0-b0b60c93de29", "division_name_en": "Badr Al Janub"},
    {"division_id": "29eca695-1688-4f46-a2be-00fd1ed32f6d", "division_name_en": "Bahrah"},
    {"division_id": "f82f76a1-54ee-40d0-b22a-3d5fe7224684", "division_name_en": "Balqarn"},
    {"division_id": "1bb55b1f-4fb8-4c57-8358-579311ef9b53", "division_name_en": "Bani Hasan"},
    {"division_id": "f63d7c8e-c9a5-4561-b69e-cf08009ff90f", "division_name_en": "Baqa"},
    {"division_id": "572f8552-ed22-4222-929c-2f672b021d30", "division_name_en": "Bariq"},
    {"division_id": "8ac56cae-9e45-4875-a04e-46ece56a96da", "division_name_en": "Baysh"},
    {"division_id": "a892dc0e-f251-4992-bffb-661e9e56bb1c", "division_name_en": "Biljurashi"},
    {"division_id": "549d2373-cb26-4d19-989c-bded131863bc", "division_name_en": "Bishah"},
    {"division_id": "324894d9-7909-4de8-8575-7555a535841b", "division_name_en": "Buraydah"},
    {"division_id": "ae4d4cd8-b856-4306-820c-a4f240f0c748", "division_name_en": "Damad"},
    {"division_id": "d01b6ca9-2753-449b-8396-348188ee8a5c", "division_name_en": "Dammam Governorate"},
    {"division_id": "02d74160-98f2-40e3-8f96-af30f6d41726", "division_name_en": "Dariyah"},
    {"division_id": "4658ab80-404e-49e7-90b1-8b699aa16660", "division_name_en": "Dawamat Al Jandal"},
    {"division_id": "6c263792-2f10-4d67-bf3c-27719dbed32b", "division_name_en": "Dhahran Al Janub"},
    {"division_id": "8a2841d5-65e7-49c5-b24c-5a9461c8e916", "division_name_en": "Duruma"},
    {"division_id": "020b8ea5-fbac-4706-a1ec-adee6dc820e6", "division_name_en": "Farasan"},
    {"division_id": "73cec284-36ed-442f-9acb-145183c75b6a", "division_name_en": "Farat Ghamid Az Zinad"},
    {"division_id": "1778c09c-ba36-419e-97ff-1f6f9cbb9630", "division_name_en": "Fayfa"},
    {"division_id": "73690afb-a495-4a4e-91d3-f3197068dc73", "division_name_en": "Governorate of Duba"},
    {"division_id": "6792684a-8712-44b7-acd2-d25074b20a00", "division_name_en": "Governorate of Jidda"},
    {"division_id": "f615cf40-dcf7-4cdc-aba0-307a3bdef349", "division_name_en": "Hafar Al Batin Governorate"},
    {"division_id": "5871e4ba-812a-4bb2-95a8-be2120196b0f", "division_name_en": "Hail"},
    {"division_id": "724fecb9-4ca7-4e36-8b61-92c96a60b731", "division_name_en": "Haqil"},
    {"division_id": "aa4a4df7-ac92-4488-8201-c12a73681633", "division_name_en": "Harub"},
    {"division_id": "473cebda-6b8d-4b7a-af8e-6dde91aec9ed", "division_name_en": "Hawtat Bani Tamim"},
    {"division_id": "88ba7a2a-6cb7-49b6-9b26-cbfdbcabfa36", "division_name_en": "Hubuna"},
    {"division_id": "c0fe4fd1-c36c-47c1-8111-20f83e8f975f", "division_name_en": "Huraymila"},
    {"division_id": "7f703c5c-f79c-4cd1-bcb9-8906ed42a798", "division_name_en": "Jazan"},
    {"division_id": "ae54ae2f-e973-4bc2-b791-8dd079a880cd", "division_name_en": "Khamis Mushayt"},
    {"division_id": "089faa8f-2591-4f09-bbc4-2bf5665dff1e", "division_name_en": "Khaybar"},
    {"division_id": "6a1d91b7-8072-4016-aacb-cbabdf4b6996", "division_name_en": "Khobar Governorate"},
    {"division_id": "60dc7a1b-e440-47b4-9eb8-17922778bed6", "division_name_en": "Khubash"},
    {"division_id": "9c3ff62a-1559-433a-9087-5f08f5147f11", "division_name_en": "Khulays"},
    {"division_id": "e4917ca4-8167-4220-a34a-c697952d92b8", "division_name_en": "Makkah Al Mukarramah"},
    {"division_id": "fe31a13e-48fb-4857-86dd-f4b93f5f86e6", "division_name_en": "Marat"},
    {"division_id": "0d3949fa-a752-4f67-b7b4-0a74de73ad52", "division_name_en": "Mawqaq"},
    {"division_id": "7255de7e-5001-4a5e-9c85-8c5062089c9d", "division_name_en": "Missan"},
    {"division_id": "2bd46190-1744-44c6-bca7-04c02ff8099d", "division_name_en": "Muhayil"},
    {"division_id": "3b837c76-b6e6-4a15-a646-7b5d241788ff", "division_name_en": "Najran"},
    {"division_id": "7db5c2b1-8571-46ab-b890-501029718cfc", "division_name_en": "Qaryah Al Ulya Governorate"},
    {"division_id": "b8340cc6-6f09-489c-8663-dc17561167cf", "division_name_en": "Qatif Governorate"},
    {"division_id": "5f6d5542-eb28-46fe-b9fb-1ad387bf58d3", "division_name_en": "Qilwah"},
    {"division_id": "bcec67da-7c1d-4d42-84a0-1b64b34aea1e", "division_name_en": "Rabigh"},
    {"division_id": "f313cbd4-0d55-4ab7-a1bf-1b253d6baa95", "division_name_en": "Rafha"},
    {"division_id": "7f804a97-b465-44a9-a417-278965793122", "division_name_en": "Ranyah"},
    {"division_id": "2f7e3748-83bf-488e-ba11-4242719e4d86", "division_name_en": "Ras Tannurah Governorate"},
    {"division_id": "094bd026-b13e-4202-85f0-e00f8b9f4b85", "division_name_en": "Rijal Almaa"},
    {"division_id": "2e0b2e20-fb85-418f-b946-adda9ef03c66", "division_name_en": "Riyadh Al Khabra"},
    {"division_id": "320aacbf-0ea0-4b05-973d-1456ae1ad467", "division_name_en": "Riyadh governorate"},
    {"division_id": "eb8abbbe-fc28-43c4-9803-d5209f33f26f", "division_name_en": "Rumah"},
    {"division_id": "6d0b54c6-a772-4162-8148-47754a7a8fbe", "division_name_en": "Sabya"},
    {"division_id": "811df065-f6d7-4df3-aa47-dd5647702696", "division_name_en": "Sakaka"},
    {"division_id": "03a492b1-4a05-4c29-be62-75859e262041", "division_name_en": "Samtah"},
    {"division_id": "1c64c007-bcfa-4dda-89c2-0430a6379ab6", "division_name_en": "Sarat Abidah"},
    {"division_id": "89a52d39-cc83-4201-9f7c-032b7f130241", "division_name_en": "Shaqra"},
    {"division_id": "1b32a9f1-cb28-4816-a4fe-fcf69d2243b6", "division_name_en": "Sharurah"},
    {"division_id": "37c064f5-f481-44bf-b61c-b0be3bf39179", "division_name_en": "Simira"},
    {"division_id": "e89d1fa1-b504-4edf-b48b-0bf3f7bb08e9", "division_name_en": "Tabuk Governorate"},
    {"division_id": "cd5fbec3-3a53-4440-bfb4-156e8fb51590", "division_name_en": "Tanumah"},
    {"division_id": "ba553d6a-ca38-4bae-96b5-f59502873e84", "division_name_en": "Tarib"},
    {"division_id": "52eae143-d218-431e-a6d0-e2979a4e321c", "division_name_en": "Tathlith"},
    {"division_id": "5699edf3-c531-4d01-9243-6254be5b8cdb", "division_name_en": "Tayma"},
    {"division_id": "16131ecb-c142-43d2-905a-71bcdf5e42f3", "division_name_en": "Thadiq"},
    {"division_id": "7cfef10a-cdba-4595-87b1-2721fb6ae029", "division_name_en": "Thar"},
    {"division_id": "be57ffba-efa1-4a3b-bb43-f91c68e9ab78", "division_name_en": "Tubarjal"},
    {"division_id": "029def81-c20e-4140-b36e-3ef47af80500", "division_name_en": "Turayf"},
    {"division_id": "d22188b9-2b77-4e11-aec4-bb0e96a1ca57", "division_name_en": "Turubah"},
    {"division_id": "4f3fb035-aad1-4427-ab8e-088f79edd357", "division_name_en": "Umluj"},
    {"division_id": "3c4dbc00-aaa0-4046-b6c3-d0b6530f5c6d", "division_name_en": "Unayzah"},
    {"division_id": "c42d3519-cde5-46a5-9277-76a7fb407c25", "division_name_en": "Uqlat As Suqur"},
    {"division_id": "d76e53eb-e35d-476b-875c-b8d788f4577a", "division_name_en": "Uyun Al Jiwa"},
    {"division_id": "25cbc1df-5e20-41d5-bdf5-f326466b1b7c", "division_name_en": "Wadi Ad Dawasir"},
    {"division_id": "60bbd19d-aaf3-4291-8739-4d3e642b1342", "division_name_en": "Wadi Al Fara"},
    {"division_id": "3f7823e6-b4bc-4276-89d0-d68308bd1f73", "division_name_en": "Yadamah"},
    {"division_id": "406c7f7f-a227-44d7-bde2-9546347247ba", "division_name_en": "Yanbu"},
]

# ensure every record has country_code
for division in DIVISIONS:
    division["country_code"] = "KSA"


def upgrade() -> None:
    """Insert geo filter reference data."""
    op.bulk_insert(geo_filter_table, DIVISIONS)


def downgrade() -> None:
    """Delete inserted geo filter reference data."""
    division_ids = [division["division_id"] for division in DIVISIONS]
    op.execute(geo_filter_table.delete().where(geo_filter_table.c.division_id.in_(division_ids)))
