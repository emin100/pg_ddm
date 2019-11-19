--
-- PostgreSQL database dump
--


SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: mask; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA mask;


ALTER SCHEMA mask OWNER TO postgres;

--
-- Name: partial(text, integer, text, integer); Type: FUNCTION; Schema: mask; Owner: postgres
--

CREATE FUNCTION mask.partial(ov text, prefix integer, padding text, suffix integer) RETURNS text
    LANGUAGE sql IMMUTABLE
    AS $$
  SELECT substring(ov FROM 1 FOR prefix)
      || padding
      || LPAD(substring(ov FROM (length(ov)-suffix+1) FOR suffix),(length(ov)-prefix-suffix),padding);
$$;


ALTER FUNCTION mask.partial(ov text, prefix integer, padding text, suffix integer) OWNER TO postgres;

--
-- Name: partial_email(text); Type: FUNCTION; Schema: mask; Owner: postgres
--

CREATE FUNCTION mask.partial_email(ov text) RETURNS text
    LANGUAGE sql IMMUTABLE
    AS $$
  SELECT substring(regexp_replace(ov, '@.*', '') FROM 1 FOR 2)
      || '******'
      || '@'
      || substring(regexp_replace(ov, '.*@', '') FROM 1 FOR 2)
      || '******'
      || '.'
      || regexp_replace(ov, '.*\.', '') 
  ;
$$;


ALTER FUNCTION mask.partial_email(ov text) OWNER TO postgres;

--
-- Name: random_date(); Type: FUNCTION; Schema: mask; Owner: postgres
--

CREATE FUNCTION mask.random_date() RETURNS timestamp with time zone
    LANGUAGE sql
    AS $$
    SELECT mask.random_date_between('01/01/1900'::DATE,now());
$$;


ALTER FUNCTION mask.random_date() OWNER TO postgres;

--
-- Name: random_date_between(timestamp with time zone, timestamp with time zone); Type: FUNCTION; Schema: mask; Owner: postgres
--

CREATE FUNCTION mask.random_date_between(date_start timestamp with time zone, date_end timestamp with time zone) RETURNS timestamp with time zone
    LANGUAGE sql
    AS $$
    SELECT (random()*(date_end-date_start))::interval+date_start;
$$;


ALTER FUNCTION mask.random_date_between(date_start timestamp with time zone, date_end timestamp with time zone) OWNER TO postgres;

--
-- Name: random_int_between(integer, integer); Type: FUNCTION; Schema: mask; Owner: postgres
--

CREATE FUNCTION mask.random_int_between(int_start integer, int_stop integer) RETURNS integer
    LANGUAGE sql
    AS $$
    SELECT CAST ( random()*(int_stop-int_start)+int_start AS INTEGER );
$$;


ALTER FUNCTION mask.random_int_between(int_start integer, int_stop integer) OWNER TO postgres;

--
-- Name: random_phone(text); Type: FUNCTION; Schema: mask; Owner: postgres
--

CREATE FUNCTION mask.random_phone(phone_prefix text DEFAULT '0'::text) RETURNS text
    LANGUAGE sql
    AS $$
    SELECT phone_prefix || CAST((select code from mask.phone_code ORDER BY random() LIMIT 1) AS TEXT) || CAST(mask.random_int_between(1000000,9999999) AS TEXT) AS "phone";
$$;


ALTER FUNCTION mask.random_phone(phone_prefix text) OWNER TO postgres;

--
-- Name: random_string(integer); Type: FUNCTION; Schema: mask; Owner: postgres
--

CREATE FUNCTION mask.random_string(l integer) RETURNS text
    LANGUAGE sql
    AS $$
  SELECT array_to_string(
    array(
        select substr('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',((random()*(36-1)+1)::integer),1)
        from generate_series(1,l)
    ),''
  );
$$;


ALTER FUNCTION mask.random_string(l integer) OWNER TO postgres;

--
-- Name: random_zip(); Type: FUNCTION; Schema: mask; Owner: postgres
--

CREATE FUNCTION mask.random_zip() RETURNS text
    LANGUAGE sql
    AS $$
  SELECT array_to_string(
         array(
                select substr('0123456789',((random()*(10-1)+1)::integer),1)
                from generate_series(1,5)
            ),''
          );
$$;


ALTER FUNCTION mask.random_zip() OWNER TO postgres;

SET default_tablespace = '';

SET default_with_oids = false;

--
-- Name: phone_code; Type: TABLE; Schema: mask; Owner: postgres
--

CREATE TABLE mask.phone_code (
    code integer NOT NULL
);


ALTER TABLE mask.phone_code OWNER TO postgres;

--
-- Name: phone_code_code_seq; Type: SEQUENCE; Schema: mask; Owner: postgres
--

CREATE SEQUENCE mask.phone_code_code_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE mask.phone_code_code_seq OWNER TO postgres;

--
-- Name: phone_code_code_seq; Type: SEQUENCE OWNED BY; Schema: mask; Owner: postgres
--

ALTER SEQUENCE mask.phone_code_code_seq OWNED BY mask.phone_code.code;


--
-- Data for Name: phone_code; Type: TABLE DATA; Schema: mask; Owner: postgres
--

COPY mask.phone_code (code) FROM stdin;
322
272
358
242
256
228
434
248
286
364
412
424
442
342
456
326
324
232
366
288
262
274
236
482
436
388
464
362
368
282
462
414
432
372
458
318
486
478
226
348
380
416
472
312
466
266
426
374
224
376
258
284
446
222
454
438
246
212
474
352
386
332
422
344
252
384
452
264
484
346
356
428
276
354
382
338
488
378
476
370
328
\.


--
-- Name: phone_code_code_seq; Type: SEQUENCE SET; Schema: mask; Owner: postgres
--

SELECT pg_catalog.setval('mask.phone_code_code_seq', 40, true);


--
-- Name: phone_code phone_code_pkey; Type: CONSTRAINT; Schema: mask; Owner: postgres
--

ALTER TABLE ONLY mask.phone_code
    ADD CONSTRAINT phone_code_pkey PRIMARY KEY (code);


--
-- PostgreSQL database dump complete
--

