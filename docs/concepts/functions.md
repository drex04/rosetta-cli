# Functions

Rosetta uses the [Function Ontology (FnO)](https://fno.io/) to declare data
transformation functions that execute during `rosetta transform`. Functions
handle type casting, unit conversion, and custom transformations.

## How functions flow

```
rosetta suggest → SSSOM (conversion_function column) → rosetta compile → YARRRML → rosetta transform
```

`rosetta suggest` auto-populates `conversion_function` based on policies in
`rosetta.toml`. The compiled YARRRML references FnO function IRIs. At
transform time, morph-kgc resolves these IRIs to Python UDF implementations.

## Builtin functions

Rosetta ships with 11 builtin functions:

### Type casts (GREL namespace)

| Function | Input | Output | Description |
|----------|-------|--------|-------------|
| `grel:math_round` | `xsd:decimal` | `xsd:integer` | Round to nearest integer |
| `grel:math_floor` | `xsd:decimal` | `xsd:integer` | Floor to integer |
| `grel:math_ceil` | `xsd:decimal` | `xsd:integer` | Ceiling to integer |
| `grel:string_toNumber` | `xsd:string` | `xsd:double` | Parse string to number |
| `grel:string_toString` | `xsd:anySimpleType` | `xsd:string` | Convert any value to string |

### Unit conversions (rosetta namespace)

| Function | Input | Output | Description |
|----------|-------|--------|-------------|
| `rfns:meterToFoot` | `xsd:decimal` | `xsd:decimal` | Meters → feet |
| `rfns:footToMeter` | `xsd:decimal` | `xsd:decimal` | Feet → meters |
| `rfns:kgToPound` | `xsd:decimal` | `xsd:decimal` | Kilograms → pounds |
| `rfns:poundToKg` | `xsd:decimal` | `xsd:decimal` | Pounds → kilograms |
| `rfns:celsiusToFahrenheit` | `xsd:decimal` | `xsd:decimal` | Celsius → Fahrenheit |
| `rfns:kelvinToCelsius` | `xsd:decimal` | `xsd:decimal` | Kelvin → Celsius |

Namespace prefixes:

- `grel:` = `http://users.ugent.be/~bjdmeest/function/grel.ttl#`
- `rfns:` = `https://rosetta.interop/functions#`

## Custom functions

You can extend rosetta with custom functions by:

1. **Declaring** the function's type signature in a `.fno.ttl` file
2. **Implementing** the function in a Python UDF file
3. **Registering** both in `rosetta.toml`

### Step 1: Declare the function

Create a Turtle file (e.g., `my_functions.fno.ttl`):

```turtle
@prefix fno:     <https://w3id.org/function/ontology#> .
@prefix xsd:     <http://www.w3.org/2001/XMLSchema#> .
@prefix ex:      <http://example.org/transforms#> .
@prefix rdf:     <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

ex:normalizeCallsign
    a fno:Function ;
    fno:name "normalizeCallsign" ;
    fno:expects ( [ a fno:Parameter ; fno:predicate ex:input ; fno:type xsd:string ] ) ;
    fno:returns ( [ a fno:Output ; fno:predicate ex:output ; fno:type xsd:string ] ) .
```

The inline blank-node list syntax (`fno:expects ( [...] )`) is required — other
Turtle encodings may not resolve correctly.

### Step 2: Implement the UDF

Create a Python file (e.g., `my_udfs.py`):

```python
try:
    from morph_kgc.udfs import udf
except ImportError:
    def udf(**kwargs):
        def decorator(fn):
            return fn
        return decorator

@udf(
    fun_id="http://example.org/transforms#normalizeCallsign",
    value="http://example.org/transforms#input",
)
def normalize_callsign(value):
    return value.strip().upper().replace(" ", "-")
```

The `fun_id` must match the full IRI of the function declared in the `.fno.ttl`
file. The `value` parameter corresponds to the `fno:predicate` of the function's
input parameter.

Guard the `morph_kgc` import with `try/except ImportError` so the file remains
importable in environments without morph-kgc installed.

!!! warning "Duplicate fun_id"
    If multiple UDF files declare the same `fun_id`, morph-kgc behavior is
    undefined. Ensure each function IRI is unique across all UDF files
    (builtin and custom).

### Step 3: Register in rosetta.toml

```toml
[functions]
declarations = ["my_functions.fno.ttl"]
udfs = ["my_udfs.py"]
```

Paths are relative to the current working directory. Multiple files can be
listed in each array.

### How it works

- `rosetta compile` and `rosetta ledger append --dry-run` load custom
  declarations into the function library, so the lint gate validates custom
  function CURIEs alongside builtins.
- `rosetta transform` concatenates custom UDF files with the builtin UDFs
  before passing them to morph-kgc for execution.

## See also

- [`rosetta compile`](../cli/compile.md) — compiles SSSOM `conversion_function` values into YARRRML function calls
- [`rosetta transform`](../cli/transform.md) — executes UDFs via morph-kgc at materialisation time
- [Datatype handling](type-handling.md) — how types flow through the pipeline alongside functions
