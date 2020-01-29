config = {
    "run_trimmomatic": False, # Set to true or false
    "prinseq": {
        "min_len": 40, # Minimum read length. (default: {40})
        "min_qual_mean": 25, # Minimum read quality. (default: {25})
        "trim_qual_right": 25,  # Trim sequence by quality score from the 3'-end with this threshold score. (default: {25})
        "trim_qual_window": 15,     # Trim sequence by quality score from the 5'-end with this threshold score. (default: {15})
        "trim_qual_type": "mean",   # Type of quality score calculation to use. (default: {"mean"})
        "out_format": 3,    # Output format 1 (FASTA only), 2 (FASTA and QUAL), 3 (FASTQ), 4 (FASTQ and FASTA), 5 (FASTQ, FASTA and QUAL) (default: {3})
        "out_bad": "null"
        },  
    "spades": {
        "mode": "--careful",
        "cov_cutoff": "auto" 
    },
    "quast": {
        "icarus": "--no-icarus",    # TODO
        "mode": "--silent"  # TODO
    },
    "annotator": "prokka",  # Set this to "prokka" or "dfast"
    "prokka": {
        "kingdom": "Bacteria",  # TODO
        "gcode": 11 # TODO
    },
    "dfast": {
        "min_length": 0, # TODO
        "use_original_name": "true" # TODO
    },
    "mlst": {},
    "abricate": {
        "virus_database": "vfdb",
        "bacteria_database": "resfinder"
    },
    "run_blast": True,     # Set this to True or False
    "blast": {
        "dbtype": "nucl",   # TODO
        "evalue": 10e-4,    # TODO
        "outfmt": "6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore sseq" # Output format
    }
}