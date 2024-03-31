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


allPOSTCheck = """
SELECT post_id FROM posts
"""


allStoriesCheck = """
SELECT post_id FROM stories
"""

storiesDrop = """
drop table stories;
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
