-- =========================================================
--  Handy queries to run in pgAdmin during the demo
--  (Tools > Query Tool, paste a query, press F5)
-- =========================================================

-- 1. See each table
SELECT * FROM clients;
SELECT * FROM voice_actors;
SELECT * FROM projects ORDER BY project_id DESC;
SELECT * FROM auditions ORDER BY audition_id DESC;
SELECT * FROM contracts ORDER BY contract_id DESC;
SELECT * FROM reviews ORDER BY review_id DESC;

-- 2. Every audition with the actor's name and the project title (JOIN)
SELECT a.audition_id, va.full_name AS actor, p.title AS project, a.status, a.submitted_at
FROM auditions a
JOIN voice_actors va ON va.actor_id = a.actor_id
JOIN projects p      ON p.project_id = a.project_id
ORDER BY a.submitted_at DESC;

-- 3. Projects per client with how many auditions each received
SELECT c.full_name AS client, c.company_name, p.title, p.status,
       COUNT(a.audition_id) AS auditions_received
FROM projects p
JOIN clients c        ON c.client_id = p.client_id
LEFT JOIN auditions a ON a.project_id = p.project_id
GROUP BY c.full_name, c.company_name, p.title, p.status
ORDER BY c.full_name;

-- 4. How much each voice actor has earned (paid contracts only)
SELECT va.full_name, COUNT(ct.contract_id) AS paid_jobs, COALESCE(SUM(ct.amount_pkr), 0) AS total_earned_pkr
FROM voice_actors va
LEFT JOIN contracts ct ON ct.actor_id = va.actor_id AND ct.payment_status = 'Paid'
GROUP BY va.full_name
ORDER BY total_earned_pkr DESC;

-- 5. Top-rated available voice actors who speak Urdu
SELECT full_name, gender, voice_style, rating, rate_pkr
FROM voice_actors
WHERE is_available = TRUE AND languages ILIKE '%Urdu%'
ORDER BY rating DESC, rate_pkr;
