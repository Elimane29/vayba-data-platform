select * from {{ ref('listens_checked') }} where rejection_reason is not null
