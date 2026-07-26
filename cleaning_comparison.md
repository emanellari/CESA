# CESA Cleaning Comparison

This document compares the original demo workbook, [`CESA_demo_dataset.xlsx`](../../CESA_demo_dataset.xlsx), with the cleaned output, [`employ_dataset_after_cleaning.xlsx`](../../employ_dataset_after_cleaning.xlsx).

It is intended to accompany the cleaning GIF in the main README and provide a direct, inspectable before-and-after example of CESA's data-cleaning workflow.

## Files compared

| File | Purpose | Main sheet | Data rows | Columns |
|---|---|---:|---:|---:|
| `CESA_demo_dataset.xlsx` | Original dataset containing intentionally inconsistent and incomplete data | `CESA_Demo_Raw` | 180 | 27 |
| `employ_dataset_after_cleaning.xlsx` | Dataset exported after applying the cleaning configuration in CESA | `Dataset` | 160 | 43 |

The cleaned workbook contains 20 fewer records. The removed employee IDs include `EMP-1002, EMP-1008, EMP-1023, EMP-1025, EMP-1037, EMP-1058, EMP-1061, EMP-1062, …`. No new employee records were added.

## Main transformations

### 1. Missing values were completed

The cleaned output contains no empty values in the columns below:

| Column | Missing before | Missing after | Result |
|---|---:|---:|---|
| `email` | 42 | 0 | Missing addresses were generated or completed |
| `department` | 5 | 0 | Empty categories were filled |
| `work_mode` | 4 | 0 | Empty work-mode values were filled |
| `hire_date` | 5 | 0 | Missing dates were completed |
| `age` | 8 | 0 | Missing numeric values were filled |
| `years_experience` | 10 | 0 | Missing values were derived or filled |
| `training_hours` | 12 | 0 | Missing values were replaced |
| `sleep_hours` | 9 | 0 | Missing values were replaced |
| `engagement_score` | 10 | 0 | Missing scores were replaced |
| `customer_satisfaction` | 8 | 0 | Missing ratings were replaced |
| `annual_bonus_eur` | 9 | 0 | Missing bonus values were filled |
| `total_compensation_eur` | 48 | 0 | Values were calculated or filled |
| `productivity_index` | 44 | 0 | Values were calculated or filled |
| `high_performer` | 38 | 0 | Missing boolean values were completed |

### 2. Categorical values were standardised

The raw workbook contained inconsistent capitalisation and extra whitespace, for example:

- ` finance `, `FINANCE` and `Finance`
- `sales`, `SALES` and `Sales`
- ` technology `, `TECH` and `Technology`
- ` hybrid `, `HYBRID` and `Hybrid`
- ` office `, `Office` and `OFFICE`

The cleaned output standardises these values into consistent categories such as:

- `Finance`
- `Sales`
- `Technology`
- `Operations`
- `Hybrid`
- `Office`
- `Remote`

This makes grouping, filtering, visualisation, ANOVA, and chi-square analysis more reliable.

### 3. Boolean values were normalised

The original dataset used several representations for the same logical values:

```text
Y / N
YES / NO
yes / no
TRUE / FALSE
true / false
1 / 0
```

The cleaned output converts `is_manager` to real boolean values and standardises `training_completed` and `high_performer` into consistent true/false representations.

### 4. Numeric columns were converted and completed

Numeric-looking strings and empty numeric cells were converted into usable numeric values.

Examples include:

- `years_experience`
- `training_hours`
- `weekly_workload_hours`
- `sleep_hours`
- `engagement_score`
- `customer_satisfaction`
- `annual_bonus_eur`
- `total_compensation_eur`
- `productivity_index`

The result can be used directly for descriptive statistics, correlation analysis, regression, and visualisation.

### 5. Calculated fields were generated

The cleaning workflow completed derived columns that were partially empty in the original dataset.

#### Total compensation

The output completes `total_compensation_eur` using salary and bonus information.

```text
monthly salary × 12 + annual bonus
```

#### Productivity index

The output completes `productivity_index` from project volume and quality information.

```text
completed projects × quality score / 10
```

#### High performer

The output completes the `high_performer` flag from performance and customer-satisfaction conditions.

These calculated fields demonstrate that CESA can apply formulas using values from other columns instead of only replacing missing data with constants.

### 6. Multi-value skills were encoded

The original workbook stored several skills inside one text column:

```text
Python, Machine Learning, SQL
Power BI, Budgeting, Excel
Communication, CRM, Forecasting
```

In the cleaned dataset, the original `skills` column was replaced by 17 binary feature columns:

```text
apis
budgeting
crm
communication
excel
financial_modeling
forecasting
git
machine_learning
negotiation
planning
power_bi
presentation
process_mapping
python
reporting
sql
```

Each column indicates whether the employee has the corresponding skill. This transformation makes the data suitable for filtering, aggregation, statistical modelling, and machine-learning workflows.

### 7. Dates were converted into a consistent machine-readable format

The original dataset included multiple date formats, such as:

```text
2021-02-04
06/01/2009
06-23-2013
Mar 04, 2008
```

The cleaned output converts the dates into a consistent timestamp representation. This allows dates to be sorted, filtered, and used in calculations after formatting them for display.

### 8. Identifier and text formatting changed

Employee identifiers were normalised to lowercase in the cleaned output:

```text
EMP-1001 → emp-1001
```

Names and email addresses were also partially standardised by trimming whitespace and normalising case.

## Before-and-after examples

| Field | Before cleaning | After cleaning |
|---|---|---|
| `employee_id` | `EMP-1001` | `emp-1001` |
| `full_name` | `  ENEA KOLA  ` | `Enea Kola` |
| `email` | missing | `eneakola@novapulse.com` |
| `department` | ` finance ` | `Finance` |
| `work_mode` | ` hybrid ` | `Hybrid` |
| `is_manager` | `Y` | `true` |
| `training_completed` | `YES` | `True` |
| `annual_bonus_eur` | missing | `1121.17` |
| `total_compensation_eur` | missing | completed numeric value |
| `productivity_index` | missing | completed numeric value |
| `skills` | `SQL, Excel, Forecasting` | separate `sql`, `excel`, and `forecasting` columns |

## Remaining review points

The exported dataset demonstrates the cleaning workflow successfully, but a few text values still require review if the goal is a fully polished reference dataset:

- Some names still contain double spaces.
- Some names still contain punctuation such as `!`.
- Generated email addresses can inherit punctuation from an uncleaned name.
- `training_completed` is displayed as text-style `True`/`False`, while `is_manager` is stored as a native boolean.
- Dates are exported as timestamps and may need an Excel date format for easier human reading.

These points are useful for demonstrating that cleaning results should be validated before final analysis or model training.

## Summary

The example shows CESA performing a complete, column-aware cleaning workflow:

- filling missing values;
- standardising categorical data;
- normalising boolean values;
- converting numeric and date fields;
- generating formula-based columns;
- encoding multi-value skills;
- removing selected records;
- producing a wider, analysis-ready dataset.

The original and cleaned Excel files can be opened directly to inspect every transformation beyond what is visible in the animated demo.
