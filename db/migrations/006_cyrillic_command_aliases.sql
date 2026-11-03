ALTER TABLE public.command_aliases
    DROP CONSTRAINT IF EXISTS command_aliases_alias_check;

ALTER TABLE public.command_aliases
    ADD CONSTRAINT command_aliases_alias_check
    CHECK (
        alias = lower(alias)
        AND alias ~ '^[[:alpha:]][[:alnum:]_]{0,19}$'
    );
