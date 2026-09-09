DO $$ 
BEGIN 
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='job_role') THEN
        ALTER TABLE users ADD COLUMN job_role VARCHAR(100);
    END IF;
END $$;
