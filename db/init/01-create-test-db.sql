-- db 볼륨이 비어 있는 첫 실행 때만 POSTGRES_USER로 실행된다.
-- 테스트 DB만 만든다. 테이블은 Alembic이 만들므로 여기에 두지 않는다.
CREATE DATABASE patron_test;
