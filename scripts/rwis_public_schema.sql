-- ============================================
-- RWIS 테스트 스키마 및 데이터 생성 스크립트
-- PostgreSQL - PUBLIC 스키마 버전
-- ============================================

-- 기존 테이블 삭제 (의존성 순서 역순)
DROP TABLE IF EXISTS rdf01hh_tb CASCADE;
DROP TABLE IF EXISTS rdr01mi_tb_old CASCADE;
DROP TABLE IF EXISTS rdievent_tb CASCADE;
DROP TABLE IF EXISTS rdzgahighlist_tb CASCADE;
DROP TABLE IF EXISTS rdzgalist_tb CASCADE;
DROP TABLE IF EXISTS rditag_tb CASCADE;
DROP TABLE IF EXISTS rditagunit_tb CASCADE;
DROP TABLE IF EXISTS rdisaup_tb CASCADE;
DROP TABLE IF EXISTS rdzgacode_tb CASCADE;

-- ============================================
-- 1. RDZGACODE_TB (사업장코드)
-- ============================================
CREATE TABLE rdzgacode_tb (
    wqe_suj_code VARCHAR(20) NOT NULL PRIMARY KEY,
    rwis_suj_code VARCHAR(20),
    krm_suj_code VARCHAR(20),
    suj_name VARCHAR(20),
    order_num INTEGER
);

COMMENT ON TABLE rdzgacode_tb IS '사업장코드';
COMMENT ON COLUMN rdzgacode_tb.wqe_suj_code IS 'WQE 정수장 코드';
COMMENT ON COLUMN rdzgacode_tb.rwis_suj_code IS 'RWIS 정수장 코드';
COMMENT ON COLUMN rdzgacode_tb.krm_suj_code IS 'KRM 정수장 코드';
COMMENT ON COLUMN rdzgacode_tb.suj_name IS '정수장명';
COMMENT ON COLUMN rdzgacode_tb.order_num IS '정렬순서';

-- ============================================
-- 2. RDISAUP_TB (사업장)
-- ============================================
CREATE TABLE rdisaup_tb (
    suj_code CHAR(3) NOT NULL,
    suj_name VARCHAR(60) NOT NULL,
    bnb_code CHAR(3) NOT NULL,
    sms_code CHAR(3) NOT NULL,
    gnj_code CHAR(1) NOT NULL,
    icus VARCHAR(10),
    crdt VARCHAR(10) DEFAULT TO_CHAR(CURRENT_TIMESTAMP, 'YYYYMMDDHH24'),
    PRIMARY KEY (suj_code, gnj_code)
);

COMMENT ON TABLE rdisaup_tb IS '사업장';
COMMENT ON COLUMN rdisaup_tb.suj_code IS '사업장코드';
COMMENT ON COLUMN rdisaup_tb.suj_name IS '사업장이름';
COMMENT ON COLUMN rdisaup_tb.bnb_code IS '본부코드';
COMMENT ON COLUMN rdisaup_tb.sms_code IS '사무소코드';
COMMENT ON COLUMN rdisaup_tb.gnj_code IS '광역지방구분 (G:광역, J:지방)';
COMMENT ON COLUMN rdisaup_tb.icus IS '주소';
COMMENT ON COLUMN rdisaup_tb.crdt IS '생성일시';

-- ============================================
-- 3. RDITAGUNIT_TB (디지털/아날로그 구분정보)
-- ============================================
CREATE TABLE rditagunit_tb (
    tag_unit INTEGER NOT NULL PRIMARY KEY,
    unit_desc VARCHAR(20),
    wdims_dpoint INTEGER,
    wdims_useyn CHAR(1)
);

COMMENT ON TABLE rditagunit_tb IS '디지털/아날로그 구분정보';
COMMENT ON COLUMN rditagunit_tb.tag_unit IS '태그타입';
COMMENT ON COLUMN rditagunit_tb.unit_desc IS '태그설명';
COMMENT ON COLUMN rditagunit_tb.wdims_dpoint IS '품질포인트';
COMMENT ON COLUMN rditagunit_tb.wdims_useyn IS 'WDIMS 사용유무';

-- ============================================
-- 4. RDITAG_TB (태그 정보 테이블)
-- ============================================
CREATE TABLE rditag_tb (
    tagsn INTEGER NOT NULL PRIMARY KEY,
    bnb_code CHAR(3) NOT NULL,
    sms_code CHAR(3) NOT NULL,
    suj_code CHAR(3) NOT NULL,
    br_code CHAR(2) NOT NULL,
    kn_code CHAR(1) NOT NULL,
    gt_code CHAR(1) NOT NULL,
    gb_code CHAR(3) NOT NULL,
    tag_unit INTEGER NOT NULL,
    tag_gubun CHAR(1) NOT NULL,
    rwis_use_yn CHAR(1) NOT NULL,
    bonsa_tran_yn CHAR(1) NOT NULL,
    data_process CHAR(1) NOT NULL,
    tag_desc VARCHAR(60) NOT NULL,
    tag_alias VARCHAR(60),
    tag_src VARCHAR(4),
    tag_path VARCHAR(100),
    tag_addr VARCHAR(24),
    tag_kind VARCHAR(8),
    tag_deci INTEGER,
    adra_val NUMERIC(16,4),
    adba_val NUMERIC(16,4),
    tag_base NUMERIC(16,4),
    tag_full NUMERIC(16,4),
    dsp_base NUMERIC(16,4),
    dsp_full NUMERIC(16,4),
    alam_opti VARCHAR(3),
    limi_low NUMERIC(16,4),
    limi_high NUMERIC(16,4),
    repo_flag VARCHAR(4),
    calc_unit VARCHAR(4),
    calc_fnum VARCHAR(4),
    on_msg VARCHAR(24),
    off_msg VARCHAR(24),
    vtag_equat VARCHAR(200),
    omit_use_yn CHAR(1),
    site_name VARCHAR(4),
    gnj_code CHAR(2),
    rsuse_yn CHAR(1),
    tag_add_dc VARCHAR(30),
    node_nm VARCHAR(10),
    locgov_code2 VARCHAR(5),
    fclty_code2 CHAR(4)
);

COMMENT ON TABLE rditag_tb IS '태그 정보 테이블';
COMMENT ON COLUMN rditag_tb.tagsn IS '태그번호';
COMMENT ON COLUMN rditag_tb.bnb_code IS '유역본부코드';
COMMENT ON COLUMN rditag_tb.sms_code IS '사무소코드';
COMMENT ON COLUMN rditag_tb.suj_code IS '사업장코드';
COMMENT ON COLUMN rditag_tb.br_code IS '변량코드';
COMMENT ON COLUMN rditag_tb.kn_code IS '기능코드';
COMMENT ON COLUMN rditag_tb.gt_code IS '계통코드';
COMMENT ON COLUMN rditag_tb.gb_code IS '구분코드(중복방지)';
COMMENT ON COLUMN rditag_tb.tag_unit IS '단위';
COMMENT ON COLUMN rditag_tb.tag_gubun IS '태그 구분 코드';
COMMENT ON COLUMN rditag_tb.rwis_use_yn IS '태그 사용여부';
COMMENT ON COLUMN rditag_tb.bonsa_tran_yn IS '본사 전송 여부';
COMMENT ON COLUMN rditag_tb.data_process IS '데이터처리방식';
COMMENT ON COLUMN rditag_tb.tag_desc IS '태그 설명';
COMMENT ON COLUMN rditag_tb.tag_alias IS '태그매핑주소';
COMMENT ON COLUMN rditag_tb.tag_full IS '유효상한값';
COMMENT ON COLUMN rditag_tb.dsp_base IS '표시하한값';
COMMENT ON COLUMN rditag_tb.dsp_full IS '표시상한값';
COMMENT ON COLUMN rditag_tb.limi_low IS '태그 하한값';
COMMENT ON COLUMN rditag_tb.limi_high IS '태그 상한값';
COMMENT ON COLUMN rditag_tb.gnj_code IS '광역지방구분코드';

-- ============================================
-- 5. RDZGALIST_TB (사업장리스트)
-- ============================================
CREATE TABLE rdzgalist_tb (
    wqe_suj_code VARCHAR(20) NOT NULL PRIMARY KEY,
    process_div VARCHAR(20),
    krm_level VARCHAR(20),
    ga_alert_yn VARCHAR(20),
    ga_alert_level VARCHAR(20),
    intake_yn VARCHAR(20),
    intake_location VARCHAR(20),
    intake_depth VARCHAR(20),
    ga_barrier_yn VARCHAR(20),
    pac_max_rate VARCHAR(20),
    pac_rate VARCHAR(20),
    pac_daily_quantity VARCHAR(20),
    pac_stock_quantity VARCHAR(20),
    pac_stock_day VARCHAR(20),
    floc_rate VARCHAR(20),
    pre_cl_rate VARCHAR(20),
    mid_cl_rate VARCHAR(20),
    hcl_way VARCHAR(20),
    wonsu_geosmin_value VARCHAR(20),
    wonsu_geosmin_date VARCHAR(20),
    wonsu_geosmin_period VARCHAR(20),
    wonsu_2mib_value VARCHAR(20),
    wonsu_2mib_date VARCHAR(20),
    wonsu_2mib_period VARCHAR(20),
    wonsu_toxic_value VARCHAR(20),
    wonsu_toxic_date VARCHAR(20),
    wonsu_toxic_period VARCHAR(20),
    jeongsu_taste_smell VARCHAR(20),
    jeongsu_geosmin_value VARCHAR(20),
    jeongsu_geosmin_date VARCHAR(20),
    jeongsu_geosmin_period VARCHAR(20),
    jeongsu_2mib_value VARCHAR(20),
    jeongsu_2mib_date VARCHAR(20),
    jeongsu_2mib_period VARCHAR(20),
    jeongsu_toxic_value VARCHAR(20),
    jeongsu_toxic_date VARCHAR(20),
    jeongsu_toxic_period VARCHAR(20),
    h2o2_rate VARCHAR(20),
    pre_o3_rate VARCHAR(20),
    post_o3_rate VARCHAR(20),
    uv_oper_rate VARCHAR(20),
    order_num INTEGER
);

COMMENT ON TABLE rdzgalist_tb IS '사업장리스트';
COMMENT ON COLUMN rdzgalist_tb.wqe_suj_code IS 'WQE 정수장 코드';
COMMENT ON COLUMN rdzgalist_tb.process_div IS '공정구분 (일반/후오존/전오존/UV)';
COMMENT ON COLUMN rdzgalist_tb.krm_level IS 'KRM 위기 단계 (평시/관심/주의)';
COMMENT ON COLUMN rdzgalist_tb.ga_alert_yn IS '조류경보 대상 여부';
COMMENT ON COLUMN rdzgalist_tb.ga_alert_level IS '조류경보 발령단계';
COMMENT ON COLUMN rdzgalist_tb.intake_yn IS '선택취수 가능 여부';
COMMENT ON COLUMN rdzgalist_tb.intake_location IS '선택취수 위치(표층/중층/심층)';
COMMENT ON COLUMN rdzgalist_tb.intake_depth IS '취수 수심';
COMMENT ON COLUMN rdzgalist_tb.ga_barrier_yn IS '조류 차단막 설치 여부';
COMMENT ON COLUMN rdzgalist_tb.pac_rate IS '분말활성탄 주입률';
COMMENT ON COLUMN rdzgalist_tb.floc_rate IS '응집제 주입률';
COMMENT ON COLUMN rdzgalist_tb.pre_cl_rate IS '전염소 주입률';
COMMENT ON COLUMN rdzgalist_tb.mid_cl_rate IS '중염소 주입률';

-- ============================================
-- 6. RDZGAHIGHLIST_TB (상한값리스트)
-- ============================================
CREATE TABLE rdzgahighlist_tb (
    wqe_suj_code VARCHAR(20) NOT NULL PRIMARY KEY,
    process_div VARCHAR(20),
    krm_level VARCHAR(20),
    ga_alert_yn VARCHAR(20),
    ga_alert_level VARCHAR(20),
    intake_yn VARCHAR(20),
    intake_location VARCHAR(20),
    intake_depth VARCHAR(20),
    ga_barrier_yn VARCHAR(20),
    floc_rate VARCHAR(20),
    pre_cl_rate VARCHAR(20),
    mid_cl_rate VARCHAR(20),
    hcl_way VARCHAR(20),
    wonsu_geosmin_value VARCHAR(20),
    wonsu_geosmin_date VARCHAR(20),
    wonsu_geosmin_period VARCHAR(20),
    wonsu_2mib_value VARCHAR(20),
    wonsu_2mib_date VARCHAR(20),
    wonsu_2mib_period VARCHAR(20),
    wonsu_toxic_value VARCHAR(20),
    wonsu_toxic_date VARCHAR(20),
    wonsu_toxic_period VARCHAR(20),
    jeongsu_taste_smell VARCHAR(20),
    jeongsu_geosmin_value VARCHAR(20),
    jeongsu_geosmin_date VARCHAR(20),
    jeongsu_geosmin_period VARCHAR(20),
    jeongsu_2mib_value VARCHAR(20),
    jeongsu_2mib_date VARCHAR(20),
    jeongsu_2mib_period VARCHAR(20),
    jeongsu_toxic_value VARCHAR(20),
    jeongsu_toxic_date VARCHAR(20),
    jeongsu_toxic_period VARCHAR(20),
    pre_o3_rate VARCHAR(20),
    post_o3_rate VARCHAR(20),
    h2o2_rate VARCHAR(20),
    uv_oper_rate VARCHAR(20),
    order_num INTEGER
);

COMMENT ON TABLE rdzgahighlist_tb IS '상한값리스트';
COMMENT ON COLUMN rdzgahighlist_tb.wqe_suj_code IS 'WQE 정수장 코드';
COMMENT ON COLUMN rdzgahighlist_tb.process_div IS '공정구분';
COMMENT ON COLUMN rdzgahighlist_tb.krm_level IS 'KRM 위기 단계';

-- ============================================
-- 7. RDR01MI_TB_OLD (01분 원시 데이터)
-- ============================================
CREATE TABLE rdr01mi_tb_old (
    log_time CHAR(12) NOT NULL,
    tagsn INTEGER NOT NULL,
    val NUMERIC(16,4) NOT NULL,
    PRIMARY KEY (log_time, tagsn)
);

COMMENT ON TABLE rdr01mi_tb_old IS '01분 원시 데이터';
COMMENT ON COLUMN rdr01mi_tb_old.log_time IS '저장시간 (YYYYMMDDHHMM)';
COMMENT ON COLUMN rdr01mi_tb_old.tagsn IS '태그번호';
COMMENT ON COLUMN rdr01mi_tb_old.val IS '측정값';

-- ============================================
-- 8. RDF01HH_TB (시간테이블)
-- ============================================
CREATE TABLE rdf01hh_tb (
    log_time CHAR(10) NOT NULL,
    tagsn INTEGER NOT NULL,
    val NUMERIC(16,4) NOT NULL,
    fst_val NUMERIC(16,4),
    PRIMARY KEY (tagsn, log_time)
);

COMMENT ON TABLE rdf01hh_tb IS '시간테이블 (1시간 단위 집계)';
COMMENT ON COLUMN rdf01hh_tb.log_time IS '저장시간 (YYYYMMDDHH)';
COMMENT ON COLUMN rdf01hh_tb.tagsn IS '태그번호';
COMMENT ON COLUMN rdf01hh_tb.val IS '집계값';
COMMENT ON COLUMN rdf01hh_tb.fst_val IS '최초값';

-- ============================================
-- 9. RDIEVENT_TB (이벤트)
-- ============================================
CREATE TABLE rdievent_tb (
    occur_time VARCHAR(14) NOT NULL,
    event_type VARCHAR(3) NOT NULL,
    proc_name VARCHAR(60) NOT NULL,
    proc_type VARCHAR(20) NOT NULL,
    event_id VARCHAR(6),
    user_id VARCHAR(20),
    machine_name VARCHAR(20),
    event_descr VARCHAR(1024)
);

COMMENT ON TABLE rdievent_tb IS '이벤트';
COMMENT ON COLUMN rdievent_tb.occur_time IS '발생시간';
COMMENT ON COLUMN rdievent_tb.event_type IS '이벤트 타입';
COMMENT ON COLUMN rdievent_tb.proc_name IS '프로시저명';
COMMENT ON COLUMN rdievent_tb.proc_type IS '프로시저형식';
COMMENT ON COLUMN rdievent_tb.event_id IS '이벤트ID';
COMMENT ON COLUMN rdievent_tb.user_id IS '사용자ID';
COMMENT ON COLUMN rdievent_tb.machine_name IS '기기명';
COMMENT ON COLUMN rdievent_tb.event_descr IS '이벤트설명';

-- ============================================
-- 테스트 데이터 삽입
-- ============================================

-- 1. RDZGACODE_TB (사업장코드) 테스트 데이터
INSERT INTO rdzgacode_tb (wqe_suj_code, rwis_suj_code, krm_suj_code, suj_name, order_num) VALUES
('WQE001', 'R001', 'K001', '팔당정수장', 1),
('WQE002', 'R002', 'K002', '청주정수장', 2),
('WQE003', 'R003', 'K003', '대전정수장', 3),
('WQE004', 'R004', 'K004', '구미정수장', 4),
('WQE005', 'R005', 'K005', '부산정수장', 5),
('WQE006', 'R006', 'K006', '광주정수장', 6),
('WQE007', 'R007', 'K007', '춘천정수장', 7),
('WQE008', 'R008', 'K008', '원주정수장', 8),
('WQE009', 'R009', 'K009', '강릉정수장', 9),
('WQE010', 'R010', 'K010', '속초정수장', 10);

-- 2. RDISAUP_TB (사업장) 테스트 데이터
INSERT INTO rdisaup_tb (suj_code, suj_name, bnb_code, sms_code, gnj_code, icus) VALUES
('001', '팔당정수장', 'SUD', 'SU1', 'G', '경기도'),
('002', '청주정수장', 'CHU', 'CH1', 'G', '충북'),
('003', '대전정수장', 'DAE', 'DA1', 'G', '대전'),
('004', '구미정수장', 'GYB', 'GY1', 'G', '경북'),
('005', '부산정수장', 'GYN', 'GN1', 'G', '경남'),
('006', '광주정수장', 'JNM', 'JN1', 'G', '전남'),
('007', '춘천정수장', 'GWN', 'GW1', 'G', '강원'),
('101', '수원정수장', 'SUD', 'SU2', 'J', '경기도'),
('102', '천안정수장', 'CHU', 'CH2', 'J', '충남'),
('103', '전주정수장', 'JNB', 'JB1', 'J', '전북');

-- 3. RDITAGUNIT_TB (태그단위) 테스트 데이터
INSERT INTO rditagunit_tb (tag_unit, unit_desc, wdims_dpoint, wdims_useyn) VALUES
(1, 'm3/h', 2, 'Y'),
(2, 'mg/L', 3, 'Y'),
(3, 'NTU', 2, 'Y'),
(4, '℃', 1, 'Y'),
(5, 'pH', 2, 'Y'),
(6, 'mg/L', 3, 'Y'),
(7, '%', 1, 'Y'),
(8, 'm', 2, 'Y'),
(9, 'kW', 1, 'Y'),
(10, 'ppm', 2, 'Y'),
(100, 'ON/OFF', 0, 'Y'),
(101, '상태', 0, 'Y');

-- 4. RDITAG_TB (태그정보) 테스트 데이터
INSERT INTO rditag_tb (tagsn, bnb_code, sms_code, suj_code, br_code, kn_code, gt_code, gb_code, tag_unit, tag_gubun, rwis_use_yn, bonsa_tran_yn, data_process, tag_desc, tag_alias, tag_deci, tag_base, tag_full, dsp_base, dsp_full, limi_low, limi_high, gnj_code) VALUES
(100001, 'SUD', 'SU1', '001', 'FL', 'A', '1', '001', 1, 'A', 'Y', 'Y', 'A', '팔당 취수유량', 'PD_INTAKE_FLOW', 2, 0, 50000, 0, 50000, 1000, 45000, 'G '),
(100002, 'SUD', 'SU1', '001', 'TB', 'A', '1', '002', 3, 'A', 'Y', 'Y', 'A', '팔당 원수탁도', 'PD_RAW_TURB', 3, 0, 100, 0, 100, 0, 50, 'G '),
(100003, 'SUD', 'SU1', '001', 'PH', 'A', '1', '003', 5, 'A', 'Y', 'Y', 'A', '팔당 원수pH', 'PD_RAW_PH', 2, 0, 14, 0, 14, 6.5, 8.5, 'G '),
(100004, 'SUD', 'SU1', '001', 'TP', 'A', '1', '004', 4, 'A', 'Y', 'Y', 'A', '팔당 원수수온', 'PD_RAW_TEMP', 1, 0, 40, 0, 40, 0, 35, 'G '),
(100005, 'SUD', 'SU1', '001', 'CL', 'A', '2', '001', 2, 'A', 'Y', 'Y', 'A', '팔당 정수잔류염소', 'PD_CL_RESIDUAL', 3, 0, 5, 0, 5, 0.1, 4.0, 'G '),
(100006, 'SUD', 'SU1', '001', 'TB', 'A', '2', '002', 3, 'A', 'Y', 'Y', 'A', '팔당 정수탁도', 'PD_TREAT_TURB', 3, 0, 10, 0, 10, 0, 0.5, 'G '),
(200001, 'CHU', 'CH1', '002', 'FL', 'A', '1', '001', 1, 'A', 'Y', 'Y', 'A', '청주 취수유량', 'CJ_INTAKE_FLOW', 2, 0, 30000, 0, 30000, 500, 28000, 'G '),
(200002, 'CHU', 'CH1', '002', 'TB', 'A', '1', '002', 3, 'A', 'Y', 'Y', 'A', '청주 원수탁도', 'CJ_RAW_TURB', 3, 0, 100, 0, 100, 0, 50, 'G '),
(200003, 'CHU', 'CH1', '002', 'PH', 'A', '1', '003', 5, 'A', 'Y', 'Y', 'A', '청주 원수pH', 'CJ_RAW_PH', 2, 0, 14, 0, 14, 6.5, 8.5, 'G '),
(300001, 'DAE', 'DA1', '003', 'FL', 'A', '1', '001', 1, 'A', 'Y', 'Y', 'A', '대전 취수유량', 'DJ_INTAKE_FLOW', 2, 0, 25000, 0, 25000, 500, 23000, 'G '),
(300002, 'DAE', 'DA1', '003', 'TB', 'A', '1', '002', 3, 'A', 'Y', 'Y', 'A', '대전 원수탁도', 'DJ_RAW_TURB', 3, 0, 100, 0, 100, 0, 50, 'G '),
(400001, 'GYB', 'GY1', '004', 'FL', 'A', '1', '001', 1, 'A', 'Y', 'Y', 'A', '구미 취수유량', 'GM_INTAKE_FLOW', 2, 0, 20000, 0, 20000, 300, 18000, 'G '),
(500001, 'GYN', 'GN1', '005', 'FL', 'A', '1', '001', 1, 'A', 'Y', 'Y', 'A', '부산 취수유량', 'BS_INTAKE_FLOW', 2, 0, 40000, 0, 40000, 800, 38000, 'G '),
(600001, 'JNM', 'JN1', '006', 'FL', 'A', '1', '001', 1, 'A', 'Y', 'Y', 'A', '광주 취수유량', 'GJ_INTAKE_FLOW', 2, 0, 35000, 0, 35000, 600, 32000, 'G '),
(700001, 'GWN', 'GW1', '007', 'FL', 'A', '1', '001', 1, 'A', 'Y', 'Y', 'A', '춘천 취수유량', 'CC_INTAKE_FLOW', 2, 0, 15000, 0, 15000, 200, 14000, 'G ');

-- 5. RDZGALIST_TB (사업장리스트) 테스트 데이터
INSERT INTO rdzgalist_tb (wqe_suj_code, process_div, krm_level, ga_alert_yn, ga_alert_level, intake_yn, intake_location, intake_depth, ga_barrier_yn, pac_max_rate, pac_rate, pac_daily_quantity, pac_stock_quantity, pac_stock_day, floc_rate, pre_cl_rate, mid_cl_rate, hcl_way, wonsu_geosmin_value, wonsu_geosmin_date, wonsu_geosmin_period, wonsu_2mib_value, wonsu_2mib_date, wonsu_2mib_period, jeongsu_taste_smell, jeongsu_geosmin_value, jeongsu_geosmin_date, jeongsu_geosmin_period, h2o2_rate, pre_o3_rate, post_o3_rate, uv_oper_rate, order_num) VALUES
('WQE001', '일반', '평시', '대상', '-', '가능', '중층', '5m', '정상', '50', '25', '10', '500', '50', '35', '1.2', '0.8', '전용', '8', '20260105', '주별', '5', '20260105', '주별', '정상', '3', '20260105', '주별', '-', '-', '-', '-', 1),
('WQE002', '후오존', '평시', '대상', '-', '가능', '심층', '8m', '정상', '40', '20', '8', '400', '50', '32', '1.0', '0.6', '전용', '6', '20260105', '주별', '4', '20260105', '주별', '정상', '2', '20260105', '주별', '-', '1.5', '0.8', '-', 2),
('WQE003', '전오존', '관심', '대상', '관심', '가능', '표층', '3m', '고정', '45', '30', '12', '450', '37', '38', '1.5', '1.0', '전염소', '12', '20260104', '일별', '8', '20260104', '일별', '미약', '5', '20260104', '일별', '-', '2.0', '-', '-', 3),
('WQE004', 'UV', '평시', '-', '-', '불가', '-', '-', '미설치', '30', '15', '5', '300', '60', '28', '0.8', '0.5', '-', '5', '20260103', '월별', '3', '20260103', '월별', '정상', '2', '20260103', '월별', '-', '-', '-', '95', 4),
('WQE005', '일반', '주의', '대상', '주의', '가능', '심층', '10m', '정상', '60', '40', '15', '600', '40', '42', '1.8', '1.2', '전용', '18', '20260105', '일별', '12', '20260105', '일별', '이상', '8', '20260105', '일별', '2.5', '-', '-', '-', 5),
('WQE006', '후오존', '평시', '대상', '-', '가능', '중층', '6m', '정상', '35', '18', '7', '350', '50', '30', '1.1', '0.7', '전용', '7', '20260105', '주별', '4', '20260105', '주별', '정상', '3', '20260105', '주별', '-', '1.2', '0.6', '-', 6),
('WQE007', '일반', '평시', '-', '-', '가능', '표층', '2m', '미설치', '25', '10', '4', '250', '62', '25', '0.9', '0.5', '전염소', '4', '20260105', '월별', '2', '20260105', '월별', '정상', '1', '20260105', '월별', '-', '-', '-', '-', 7);

-- 6. RDZGAHIGHLIST_TB (상한값리스트) 테스트 데이터
INSERT INTO rdzgahighlist_tb (wqe_suj_code, process_div, krm_level, ga_alert_yn, ga_alert_level, intake_yn, intake_location, intake_depth, ga_barrier_yn, floc_rate, pre_cl_rate, mid_cl_rate, hcl_way, wonsu_geosmin_value, wonsu_geosmin_date, wonsu_geosmin_period, wonsu_2mib_value, wonsu_2mib_date, wonsu_2mib_period, jeongsu_taste_smell, jeongsu_geosmin_value, jeongsu_geosmin_date, jeongsu_geosmin_period, pre_o3_rate, post_o3_rate, h2o2_rate, uv_oper_rate, order_num) VALUES
('WQE001', '일반', '주의', '-', '조류대발생', '-', '-', '15m', '-', '60', '2.5', '1.5', '-', '20', '-', '-', '15', '-', '-', '-', '10', '-', '-', '-', '-', '5.0', '-', 1),
('WQE002', '후오존', '주의', '-', '조류대발생', '-', '-', '15m', '-', '55', '2.0', '1.2', '-', '18', '-', '-', '12', '-', '-', '-', '8', '-', '-', '3.0', '2.0', '-', '-', 2),
('WQE003', '전오존', '주의', '-', '조류대발생', '-', '-', '10m', '-', '58', '2.5', '1.5', '-', '25', '-', '-', '18', '-', '-', '-', '12', '-', '-', '4.0', '-', '-', '-', 3),
('WQE004', 'UV', '주의', '-', '-', '-', '-', '-', '-', '50', '1.5', '1.0', '-', '15', '-', '-', '10', '-', '-', '-', '6', '-', '-', '-', '-', '-', '100', 4),
('WQE005', '일반', '주의', '-', '조류대발생', '-', '-', '15m', '-', '65', '3.0', '2.0', '-', '30', '-', '-', '20', '-', '-', '-', '15', '-', '-', '-', '-', '5.0', '-', 5);

-- 7. RDR01MI_TB_OLD (1분 원시데이터) 테스트 데이터 - 최근 데이터
INSERT INTO rdr01mi_tb_old (log_time, tagsn, val) VALUES
-- 2026년 1월 7일 데이터
('202601070900', 100001, 42500.5000),
('202601070900', 100002, 3.2500),
('202601070900', 100003, 7.4500),
('202601070900', 100004, 8.5000),
('202601070900', 100005, 0.6500),
('202601070900', 100006, 0.1200),
('202601070900', 200001, 25800.2500),
('202601070900', 200002, 2.8500),
('202601070900', 200003, 7.5200),
('202601070901', 100001, 42600.7500),
('202601070901', 100002, 3.3000),
('202601070901', 100003, 7.4200),
('202601070901', 100004, 8.6000),
('202601070901', 100005, 0.6800),
('202601070901', 100006, 0.1150),
('202601070902', 100001, 42450.0000),
('202601070902', 100002, 3.1500),
('202601070902', 100003, 7.4800),
('202601070903', 100001, 42700.2500),
('202601070903', 100002, 3.4000),
('202601071000', 100001, 43100.5000),
('202601071000', 100002, 3.5500),
('202601071000', 100003, 7.4000),
('202601071000', 100004, 9.2000),
('202601071000', 100005, 0.7000),
('202601071000', 100006, 0.1100);

-- 8. RDF01HH_TB (시간별 집계) 테스트 데이터
INSERT INTO rdf01hh_tb (log_time, tagsn, val, fst_val) VALUES
-- 2026년 1월 6일 시간별 데이터
('2026010600', 100001, 41500.0000, 41200.0000),
('2026010601', 100001, 41800.0000, 41500.0000),
('2026010602', 100001, 42000.0000, 41800.0000),
('2026010603', 100001, 42200.0000, 42000.0000),
('2026010604', 100001, 42100.0000, 42200.0000),
('2026010605', 100001, 41900.0000, 42100.0000),
('2026010606', 100001, 42300.0000, 41900.0000),
('2026010607', 100001, 42500.0000, 42300.0000),
('2026010608', 100001, 42800.0000, 42500.0000),
('2026010609', 100001, 43000.0000, 42800.0000),
('2026010610', 100001, 43200.0000, 43000.0000),
('2026010611', 100001, 43100.0000, 43200.0000),
('2026010612', 100001, 42900.0000, 43100.0000),
('2026010600', 100002, 2.8000, 2.5000),
('2026010601', 100002, 2.9000, 2.8000),
('2026010602', 100002, 3.1000, 2.9000),
('2026010603', 100002, 3.3000, 3.1000),
('2026010604', 100002, 3.2000, 3.3000),
('2026010605', 100002, 3.0000, 3.2000),
('2026010606', 100002, 3.1500, 3.0000),
('2026010607', 100002, 3.2500, 3.1500),
('2026010608', 100002, 3.4000, 3.2500),
('2026010600', 200001, 24500.0000, 24200.0000),
('2026010601', 200001, 24800.0000, 24500.0000),
('2026010602', 200001, 25100.0000, 24800.0000),
('2026010603', 200001, 25400.0000, 25100.0000),
-- 2026년 1월 7일 시간별 데이터
('2026010700', 100001, 41800.0000, 41600.0000),
('2026010701', 100001, 42000.0000, 41800.0000),
('2026010702', 100001, 42200.0000, 42000.0000),
('2026010703', 100001, 42400.0000, 42200.0000),
('2026010704', 100001, 42350.0000, 42400.0000),
('2026010705', 100001, 42100.0000, 42350.0000),
('2026010706', 100001, 42450.0000, 42100.0000),
('2026010707', 100001, 42600.0000, 42450.0000),
('2026010708', 100001, 42750.0000, 42600.0000),
('2026010709', 100001, 42550.0000, 42500.0000),
('2026010710', 100001, 43100.0000, 43050.0000);

-- 9. RDIEVENT_TB (이벤트) 테스트 데이터
INSERT INTO rdievent_tb (occur_time, event_type, proc_name, proc_type, event_id, user_id, machine_name, event_descr) VALUES
('20260107090000', 'INF', 'DATA_COLLECT', 'BATCH', 'EV0001', 'SYSTEM', 'RWIS-SRV01', '팔당정수장 데이터 수집 시작'),
('20260107090100', 'INF', 'DATA_COLLECT', 'BATCH', 'EV0002', 'SYSTEM', 'RWIS-SRV01', '팔당정수장 데이터 수집 완료 - 6개 태그'),
('20260107090500', 'WRN', 'ALARM_CHECK', 'BATCH', 'EV0003', 'SYSTEM', 'RWIS-SRV01', '대전정수장 조류경보 관심단계 감지'),
('20260107091000', 'ERR', 'DATA_COLLECT', 'BATCH', 'EV0004', 'SYSTEM', 'RWIS-SRV02', '구미정수장 통신 오류 - 재시도 예정'),
('20260107091500', 'INF', 'DATA_COLLECT', 'BATCH', 'EV0005', 'SYSTEM', 'RWIS-SRV02', '구미정수장 통신 복구 완료'),
('20260107100000', 'INF', 'HOURLY_AGG', 'BATCH', 'EV0006', 'SYSTEM', 'RWIS-SRV01', '시간별 집계 작업 시작'),
('20260107100500', 'INF', 'HOURLY_AGG', 'BATCH', 'EV0007', 'SYSTEM', 'RWIS-SRV01', '시간별 집계 작업 완료 - 처리건수: 1250'),
('20260106080000', 'INF', 'DAILY_REPORT', 'BATCH', 'EV0008', 'SYSTEM', 'RWIS-SRV01', '일일 보고서 생성 시작'),
('20260106083000', 'INF', 'DAILY_REPORT', 'BATCH', 'EV0009', 'SYSTEM', 'RWIS-SRV01', '일일 보고서 생성 완료'),
('20260105140000', 'WRN', 'QUALITY_CHECK', 'BATCH', 'EV0010', 'ADMIN', 'RWIS-SRV01', '부산정수장 수질 주의단계 상향 조정');

-- 인덱스 생성
CREATE INDEX idx_rdr01mi_log_time ON rdr01mi_tb_old(log_time);
CREATE INDEX idx_rdr01mi_tagsn ON rdr01mi_tb_old(tagsn);
CREATE INDEX idx_rdf01hh_log_time ON rdf01hh_tb(log_time);
CREATE INDEX idx_rditag_suj_code ON rditag_tb(suj_code);
CREATE INDEX idx_rditag_bnb_code ON rditag_tb(bnb_code);
CREATE INDEX idx_rdievent_occur_time ON rdievent_tb(occur_time);
CREATE INDEX idx_rdievent_event_type ON rdievent_tb(event_type);

-- 완료 메시지
DO $$
BEGIN
    RAISE NOTICE 'RWIS 테스트 데이터 생성 완료 (public 스키마)!';
    RAISE NOTICE '생성된 테이블: rdzgacode_tb, rdisaup_tb, rditagunit_tb, rditag_tb, rdzgalist_tb, rdzgahighlist_tb, rdr01mi_tb_old, rdf01hh_tb, rdievent_tb';
END $$;



