-- T01/T02 대량 샘플 데이터
-- 전제: init_db.sql로 sample."T01"/sample."T02"가 생성되어 있음

INSERT INTO sample."T02" ("C01", "C02") VALUES
('P001', 1000.00),
('P002',  500.00),
('P003',  750.00),
('P004', 1200.00),
('P005',  300.00),
('P006',  950.00),
('P007',  200.00),
('P008',  850.00),
('P009',  400.00),
('P010',  999.99);

-- 주문(사용자ID, 주문금액, 주문일시) - 가격×수량 결과를 직접 기록
-- 사용자ID는 100~199 범위로 샘플링
INSERT INTO sample."T01" ("C01", "C02", "C03", "C04", "C05") VALUES
(101, (SELECT "C02" FROM sample."T02" WHERE "C01"='P001') * 1,  NOW() - INTERVAL '1 day',  'P001', 1),
(102, (SELECT "C02" FROM sample."T02" WHERE "C01"='P002') * 3,  NOW() - INTERVAL '2 days', 'P002', 3),
(103, (SELECT "C02" FROM sample."T02" WHERE "C01"='P003') * 2,  NOW() - INTERVAL '3 days', 'P003', 2),
(104, (SELECT "C02" FROM sample."T02" WHERE "C01"='P004') * 1,  NOW() - INTERVAL '4 days', 'P004', 1),
(105, (SELECT "C02" FROM sample."T02" WHERE "C01"='P005') * 5,  NOW() - INTERVAL '5 days', 'P005', 5),
(106, (SELECT "C02" FROM sample."T02" WHERE "C01"='P006') * 2,  NOW() - INTERVAL '6 days', 'P006', 2),
(107, (SELECT "C02" FROM sample."T02" WHERE "C01"='P007') * 7,  NOW() - INTERVAL '7 days', 'P007', 7),
(108, (SELECT "C02" FROM sample."T02" WHERE "C01"='P008') * 1,  NOW() - INTERVAL '8 days', 'P008', 1),
(109, (SELECT "C02" FROM sample."T02" WHERE "C01"='P009') * 4,  NOW() - INTERVAL '9 days', 'P009', 4),
(110, (SELECT "C02" FROM sample."T02" WHERE "C01"='P010') * 2, NOW() - INTERVAL '10 days', 'P010', 2),
(111, (SELECT "C02" FROM sample."T02" WHERE "C01"='P001') * 2, NOW() - INTERVAL '11 days', 'P001', 2),
(112, (SELECT "C02" FROM sample."T02" WHERE "C01"='P002') * 1, NOW() - INTERVAL '12 days', 'P002', 1),
(113, (SELECT "C02" FROM sample."T02" WHERE "C01"='P003') * 3, NOW() - INTERVAL '13 days', 'P003', 3),
(114, (SELECT "C02" FROM sample."T02" WHERE "C01"='P004') * 2, NOW() - INTERVAL '14 days', 'P004', 2),
(115, (SELECT "C02" FROM sample."T02" WHERE "C01"='P005') * 8, NOW() - INTERVAL '15 days', 'P005', 8),
(116, (SELECT "C02" FROM sample."T02" WHERE "C01"='P006') * 1, NOW() - INTERVAL '16 days', 'P006', 1),
(117, (SELECT "C02" FROM sample."T02" WHERE "C01"='P007') * 3, NOW() - INTERVAL '17 days', 'P007', 3),
(118, (SELECT "C02" FROM sample."T02" WHERE "C01"='P008') * 2, NOW() - INTERVAL '18 days', 'P008', 2),
(119, (SELECT "C02" FROM sample."T02" WHERE "C01"='P009') * 1, NOW() - INTERVAL '19 days', 'P009', 1),
(120, (SELECT "C02" FROM sample."T02" WHERE "C01"='P010') * 1, NOW() - INTERVAL '20 days', 'P010', 1);


