mediaCreate = """
CREATE TABLE IF NOT EXISTS medias (
	id INTEGER NOT NULL, 
	media_id INTEGER, 
	post_id INTEGER NOT NULL, 
	link VARCHAR, 
	directory VARCHAR, 
	filename VARCHAR, 
	size INTEGER, 
	api_type VARCHAR, 
	media_type VARCHAR, 
	preview INTEGER, 
	linked VARCHAR, 
	downloaded INTEGER, 
	created_at TIMESTAMP, 
	hash VARCHAR,
    model_id INTEGER,
	PRIMARY KEY (id), 
	UNIQUE (media_id,model_id)
);"""


otherCreate = """
CREATE TABLE IF NOT EXISTS others (
	id INTEGER NOT NULL,  
	post_id INTEGER NOT NULL, 
	text VARCHAR, 
	price INTEGER, 
	paid INTEGER, 
	archived BOOLEAN, 
	created_at TIMESTAMP, 
	model_id INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (post_id,model_id)
)
"""
productCreate = """
CREATE TABLE IF NOT EXISTS products (
	id INTEGER NOT NULL, 
	post_id INTEGER NOT NULL, 
	text VARCHAR, 
	price INTEGER, 
	paid INTEGER, 
	archived BOOLEAN, 
	created_at TIMESTAMP,
    title VARCHAR, 
    model_id INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (post_id,model_id)
)
"""
profilesCreate = """
CREATE TABLE IF NOT EXISTS profiles (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	username VARCHAR NOT NULL,
	PRIMARY KEY (id)
)
"""

modelsCreate = """
CREATE TABLE IF NOT EXISTS models (
	id INTEGER NOT NULL,
	model_id INTEGER NOT NULL,
	UNIQUE (model_id)
	PRIMARY KEY (id)
)
"""

storiesCreate = """
CREATE TABLE IF NOT EXISTS stories (
	id INTEGER NOT NULL, 
	post_id INTEGER NOT NULL, 
	text VARCHAR, 
	price INTEGER, 
	paid INTEGER, 
	archived BOOLEAN, 
	created_at TIMESTAMP, 
    model_id INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (post_id,model_id)
)
"""

schemaCreate = """
CREATE TABLE if not exists schema_flags (flag_name TEXT PRIMARY KEY, flag_value TEXT);
"""


postNormalCheck = """
SELECT post_id FROM posts where archived=False
"""


storiesInsert = f"""INSERT INTO 'stories'(
post_id, text,price,paid,archived,created_at,model_id)
            VALUES (?, ?,?,?,?,?,?);"""


storiesUpdate = f"""UPDATE stories
SET text = ?, price = ?, paid = ?, archived = ?, created_at = ? ,model_id=?
WHERE post_id = ?;"""


storiesAddColumnID = """
ALTER TABLE stories ADD COLUMN model_id INTEGER;
"""


storiesALLTransition = """
select post_id,text,price,paid,archived,created_at from stories
"""

allIDCheck = """
SELECT media_id FROM medias
"""

allDLIDCheck = """
SELECT media_id FROM medias where downloaded=(1)
"""

allPOSTCheck = """
SELECT post_id FROM posts
"""


allStoriesCheck = """
SELECT post_id FROM stories
"""

storiesDrop = """
drop table stories;
"""

mediaInsert = f"""INSERT INTO 'medias'(
media_id,post_id,link,api_type,media_type,preview,linked,created_at,hash,model_id)
            VALUES (?,?,?,?,?,?,?,?,?,?);"""

mediaDupeCheck = """
SELECT * FROM medias where media_id=(?)
"""

getTimelineMedia = """
SELECT * FROM medias where api_type=('Timeline') and model_id=(?)
"""

getArchivedMedia = """
SELECT * FROM medias where api_type=('Archived') and model_id=(?)
"""

getMessagesMedia = """
SELECT * FROM medias where api_type=('Message') or api_type=('Messages') and model_id=(?)
"""


mediaUpdateAPI = f"""Update 'medias'
SET
media_id=?,post_id=?,linked=?,api_type=?,media_type=?,preview=?,created_at=?,model_id=?
WHERE media_id=(?);"""


mediaUpdateDownload = f"""Update 'medias'
SET
directory=?,filename=?,size=?,downloaded=?,hash=?
WHERE media_id=(?);"""


mediaALLTransition = """
SELECT media_id,post_id,link,directory,filename,size,api_type,
media_type,preview,linked,downloaded,created_at,hash FROM medias;
"""


mediaDrop = """
drop table medias;
"""
profileDupeCheck = """
SELECT * FROM profiles where user_id=(?)
"""
profileTableCheck = """
SELECT name FROM sqlite_master WHERE type='table' AND name='profiles';
"""

profileInsert = f"""INSERT INTO 'profiles'(
user_id,username)
            VALUES (?, ?);"""

profileUpdate = f"""Update 'profiles'
SET
user_id=?,username=?
WHERE user_id=(?);"""


modelDupeCheck = """
SELECT * FROM models where model_id=(?)
"""

modelInsert = f"""
INSERT INTO models (model_id)
VALUES (?);
"""


mediaAddColumnHash = """
ALTER TABLE medias ADD COLUMN hash VARCHAR;
"""

mediaAddColumnID = """
ALTER TABLE medias ADD COLUMN model_id INTEGER;
"""


mediaDupeHashesMedia = """
WITH x AS (
    SELECT hash, size
    FROM medias
    WHERE hash IS NOT NULL AND size is not null and  WHERE hash IS NOT NULL AND size IS NOT NULL AND (media_type = ?)
)
)
SELECT hash
FROM x
GROUP BY hash, size
HAVING COUNT(*) > 1;
"""

mediaDupeHashes = """
WITH x AS (
    SELECT hash, size
    FROM medias
    WHERE hash IS NOT NULL AND size is not null and  WHERE hash IS NOT NULL AND size IS NOT NULL
)
)
SELECT hash
FROM x
GROUP BY hash, size
HAVING COUNT(*) > 1;
"""

mediaDupeFiles = """
SELECT filename
FROM medias
where hash=(?)
"""


profilesALL = """
select user_id,username from profiles
"""
profilesDrop = """
DROP TABLE profiles;
"""

otherAddColumnID = """
ALTER Table others ADD COLUMN model_id INTEGER;
"""

productsAddColumnID = """
ALTER Table products ADD COLUMN model_id INTEGER;
"""


schemaAll = """
SELECT flag_name FROM schema_flags WHERE flag_value = 1;
"""

schemaInsert = """
INSERT INTO 'schema_flags'( flag_name,flag_value)
VALUES (?,?)
"""


othersALLTransition = """
SELECT text,price,paid,archived,created_at FROM others;
"""


othersDrop = """
drop table others;
"""


othersInsert = f"""INSERT INTO 'others'(
post_id, text,price,paid,archived,
created_at,model_id)
VALUES (?, ?,?,?,?,?,?);"""


productsALLTransition = """
SELECT text,price,paid,archived,created_at FROM products;
"""


productsDrop = """
drop table products;
"""

productsInsert = f"""INSERT INTO 'products'(
post_id, text,price,paid,archived,
created_at,title,model_id)
VALUES (?, ?,?,?,?,?,?,?);"""
