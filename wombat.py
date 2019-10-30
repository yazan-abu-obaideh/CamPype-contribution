import pandas
import datetime
import os
import shutil
from subprocess import call
from Bio import SeqIO


def read_input_files(indexfile):
    """
    Gets every pair of reads on input_files.csv
    
    Arguments:
        indexfile {string} -- Filename of the file containing inputs.
    
    Returns:
        files_tuples {list of tuples} -- List of tuples each containing forward read file path, reverse read file path and file basename (just the sample number).
    """
    files_df = pandas.read_csv(indexfile, sep="\t")
    files_tuples = []
    for _, row in files_df.iterrows():
        files_tuples.append((row["Read1"], row["Read2"], str(row["Samples"])))

    return files_tuples


def trimmomatic_call(input_file1, input_file2, phred, trimfile,
                    paired_out_file1, paired_out_file2, unpaired_out_file1, unpaired_out_file2):
    """
    Trimmomatic call.
    
    Arguments:
        input_file1 {string} -- Input file forward.
        input_file2 {string} -- Input file reverse.
        phred {string} -- Trimmomatic phred parameter.
        trimfile {string} -- File with trimming sequences.
        paired_out_file1 {string} -- Forward file paired output.
        paired_out_file2 {string} -- Reverse file paired output.
        unpaired_out_file1 {string} -- Forward file unpaired output.
        unpaired_out_file2 {string} -- Reverse file unpaired output.
    
    Returns:
        {int} -- Execution state (0 if everything is all right)
    """
    arguments = ["trimmomatic", "PE", phred, input_file1, input_file2, \
                paired_out_file1, unpaired_out_file1, paired_out_file2, unpaired_out_file2, trimfile]
    return call(arguments)


def prinseq_call(input_file1, input_file2, min_len=40, min_qual_mean=25, trim_qual_right=25,
                 trim_qual_window=15, trim_qual_type="mean", out_format=3, log_name=None):
    """
    Prinseq call
    
    Arguments:
        input_file1 {string} -- Input file forward.
        input_file2 {string} -- Input file reverse.
    
    Keyword Arguments:
        min_len {int} -- Minimum read length. (default: {40})
        min_qual_mean {int} -- Minimum read quality. (default: {25})
        trim_qual_right {int} -- Trim sequence by quality score from the 3'-end with this threshold score. (default: {25})
        trim_qual_window {int} -- Trim sequence by quality score from the 5'-end with this threshold score. (default: {15})
        trim_qual_type {str} -- Type of quality score calculation to use. (default: {"mean"})
        out_format {int} -- Output format 1 (FASTA only), 2 (FASTA and QUAL), 3 (FASTQ), 4 (FASTQ and FASTA), 5 (FASTQ, FASTA and QUAL) (default: {3})
        log_name {string} -- Output log file name.
    
    Returns:
        int -- Execution state (0 if everything is all right)
    """
    arguments = ["prinseq-lite.pl", "-verbose", "-fastq", input_file1, "-fastq2", input_file2, "-min_len", min_len, \
                "-min_qual_mean", min_qual_mean, "-trim_qual_right", trim_qual_right, "-trim_qual_window", \
                trim_qual_window, "-trim_qual_type", trim_qual_type, "-out_format", out_format, "-out_bad", "null", "-log", log_name]
    return call(arguments)


def refactor_prinseq_output(input_dir, output_dir, sample):
    """
    Places prinseq output files into directories with the following structure: /OUTPUT[timestamp]/Prinseq_filtering2/sample
    
    Arguments:
        input_dir {string} -- Input directory.
        output_dir {string} -- Output directory.
        sample {string} -- Sample basename.
    
    Returns:
        {dict} -- names of refactored files. key: forward or reverse (R1 or R2), value: filename
    """
    filenames = dict()  # Files with good sequences (except singletons)
    for root, dirs, files in os.walk(input_dir):
        main_out_folder = root.split("/")[0]
        for filename in files:
            if filename.__contains__("prinseq"):
                shutil.move(os.path.join(root, filename), main_out_folder+"/"+output_dir+"/"+sample)
                if filename.startswith(sample+"_R1") and not filename.__contains__("singletons"):
                    filenames["R1"] = filename
                elif filename.startswith(sample+"_R2") and not filename.__contains__("singletons"):
                    filenames["R2"] = filename
    return filenames


def spades_call(forward_sample, reverse_sample, sample, out_dir):
    """
    Spades call
    
    Arguments:
        forward_sample {string} -- Forward sample file name.
        reverse_sample {string} -- Reverse sample file name.
        sample {string} -- Sample basename.
        out_dir {string} -- Output directory.
    
    Returns:
        {int} -- Execution state (0 if everything is all right)
    """
    arguments = ["spades.py", "-1", forward_sample, "-2", reverse_sample, "--careful", "-o", out_dir+"/"+sample]
    return call(arguments)


def contigs_trim_and_rename(contigs_file, output_dir, min_len):
    """
    Creates new fasta file filtering sequences shorter than min_len and shortening sequence identifiers.
    
    Arguments:
        contigs_file {string} -- Original contigs filename.
        output_dir {string} -- Output directory.
        min_len {int} -- Minimum sequence length.
    """
    large_sequences = []
    for record in SeqIO.parse(contigs_file, "fasta"):
        if len(record.seq) > min_len:
            record.id = "C_"+"_".join(record.id.split("_")[1:4])
            record.description = ""
            large_sequences.append(record)
    SeqIO.write(large_sequences, output_dir, "fasta")


def quast_call(input_file, output_dir, min_contig):
    """
    Quast call.
    
    Arguments:
        input_file {string} -- Input file.
        output_dir {string} -- Output directory.
        min_contig {int} -- Lower threshold for a contig length (in bp).
    
    Returns:
        {int} -- Execution state (0 if everything is all right)
    """
    arguments = ["quast", input_file, "-o", output_dir, "--min-contig", str(min_contig), "--no-icarus", "--silent"]
    return call(arguments)


def mlst_call(input_dir, output_dir, output_filename):
    """
    MLST call for every fasta file in input_dir.
    
    Arguments:
        input_dir {string} -- Input directory containing contig files.
        output_dir {string} -- Output directory.
        output_filename {string} -- Output file name.
    
    Returns:
        {int} -- Execution state (0 if everything is all right)
    """
    output_file = open(output_dir+"/"+output_filename, "w")
    
    input_filenames = []

    for root, dirs, files in os.walk(input_dir):
        for filename in files:
            if filename.endswith(".fasta"):
                input_filenames.append(input_dir+"/"+filename)

    arguments = ["mlst", *input_filenames]
    return call(arguments, stdout=output_file)


def abricate_call(input_dir, output_dir, output_filename, database):
    """
    ABRicate call.
    
    Arguments:
        input_dir {string} -- Input directory containing contig files.
        output_dir {string} -- Output directory.
        output_filename {string} -- Output file name.
        database {string} -- Database name.
    
    Returns:
        {int} -- Execution state (0 if everything is all right)
    """
    output_file = open(output_dir+"/"+output_filename, "w")
    
    input_filenames = []

    for root, dirs, files in os.walk(input_dir):
        for filename in files:
            if filename.endswith(".fasta"):
                input_filenames.append(input_dir+"/"+filename)

    arguments = ["abricate", *input_filenames, "--db", database]
    return call(arguments, stdout=output_file)

# <path to prokka> --locustag Sample_L --outdir Sample --prefix Sample --kingdom Bacteria --gcode 11 Sample.fasta
def prokka_call(locus_tag, output_dir, prefix, input_file):
    """
    Prokka call.
    
    Arguments:
        locus_tag {string} -- Locus tag prefix.
        output_dir {string} -- Output directory.
        prefix {string} -- Filename output prefix.
        input_file {string} -- Input filename.
    
    Returns:
        {int} -- Execution state (0 if everything is all right)
    """
    arguments = ["prokka", "--locustag", locus_tag, "--outdir", output_dir, "--prefix", prefix, "--kingdom", "Bacteria", "--gcode", "11", input_file]
    return call(arguments)

def roary_call():
    pass

if __name__ == "__main__":

    # Create output directories
    now = datetime.datetime.now()
    
    output_folder = "Workflow_OUTPUT_"+str(now.strftime('%Y%m%d_%H%M%S'))
    trimmomatic_dir = "Trimmomatic_filtering1"
    prinseq_dir = "Prinseq_filtering2"
    spades_dir = "SPAdes_assembly"
    contigs_dir = "Contigs_renamed_shorten"
    quast_dir = "Sample_assembly_statistics"
    mlst_dir = "MLST"
    abricate_vir_dir = "ABRicate_virulence_genes"
    abricate_abr_dir = "ABRicateAntibioticResistanceGenes"
    prokka_dir = "Prokka_annotation"

    os.mkdir(output_folder)
    os.mkdir(output_folder+"/"+trimmomatic_dir)
    os.mkdir(output_folder+"/"+prinseq_dir)
    os.mkdir(output_folder+"/"+spades_dir)
    os.mkdir(output_folder+"/"+contigs_dir)
    os.mkdir(output_folder+"/"+mlst_dir)
    os.mkdir(output_folder+"/"+abricate_vir_dir)
    os.mkdir(output_folder+"/"+abricate_abr_dir)
    os.mkdir(output_folder+"/"+prokka_dir)
    

    for sample1, sample2, sample_basename in read_input_files("input_files.csv"):
        # Trimmomatic call
        print(f"\nStep 1 for sequence {sample_basename}: Trimmomatic\n")
        trimmomatic_call(input_file1=sample1,
                        input_file2=sample2,
                        phred="-phred33",
                        trimfile="ILLUMINACLIP:adapters.fa:1:30:11",
                        paired_out_file1=output_folder+"/"+trimmomatic_dir+"/"+sample_basename+"_R1_paired.fastq",
                        unpaired_out_file1=output_folder+"/"+trimmomatic_dir+"/"+sample_basename+"_R1_unpaired.fastq",
                        paired_out_file2=output_folder+"/"+trimmomatic_dir+"/"+sample_basename+"_R2_paired.fastq",
                        unpaired_out_file2=output_folder+"/"+trimmomatic_dir+"/"+sample_basename+"_R2_unpaired.fastq")

        # Creates prinseq output directories
        os.mkdir(output_folder+"/"+prinseq_dir+"/"+sample_basename)

        # Prinseq call
        print("\nStep 2 for sequence {sample_basename}: Prinseq\n")
        prinseq_call(input_file1=output_folder+"/"+trimmomatic_dir+"/"+sample_basename+"_R1_paired.fastq",
                     input_file2=output_folder+"/"+trimmomatic_dir+"/"+sample_basename+"_R2_paired.fastq", 
                     min_len="40", 
                     min_qual_mean="25", 
                     trim_qual_right="25", 
                     trim_qual_window="15", 
                     trim_qual_type="mean",
                     out_format="3",
                     log_name=output_folder+"/"+prinseq_dir+"/"+sample_basename+"/"+sample_basename+".log")

        # Prinseq output files refactor
        prinseq_files = refactor_prinseq_output(output_folder+"/"+trimmomatic_dir, prinseq_dir, sample_basename)
        
        # Creates SPAdes output directories
        os.mkdir(output_folder+"/"+spades_dir+"/"+sample_basename)

        # SPAdes call
        print("\nStep 3 for sequence {sample_basename}: SPAdes\n")
        spades_call(forward_sample=output_folder+"/"+prinseq_dir+"/"+sample_basename+"/"+prinseq_files["R1"],
                    reverse_sample=output_folder+"/"+prinseq_dir+"/"+sample_basename+"/"+prinseq_files["R2"],
                    sample=sample_basename,
                    out_dir=output_folder+"/"+spades_dir)

        # Trim short contigs and shorten sequences id
        contigs_trim_and_rename(output_folder+"/"+spades_dir+"/"+sample_basename+"/"+"contigs.fasta", 
                                output_folder+"/"+contigs_dir+"/"+sample_basename+"_contigs.fasta",
                                200)

        # Creates Quast output directories
        os.mkdir(output_folder+"/"+spades_dir+"/"+sample_basename+"/"+quast_dir)

        # Quast call
        print("\nStep 4 for sequence {sample_basename}: Quast\n")
        quast_call( input_file=output_folder+"/"+contigs_dir+"/"+sample_basename+"_contigs.fasta",
                    output_dir=output_folder+"/"+spades_dir+"/"+sample_basename+"/"+quast_dir,
                    min_contig=200)

        # Prokka call
        print("\nStep 5 for sequence {sample_basename}: Prokka\n")
        prokka_call(locus_tag=sample_basename+"_L",
                    output_dir=output_folder+"/"+prokka_dir+"/"+sample_basename,
                    prefix=sample_basename,
                    input_file=output_folder+"/"+contigs_dir+"/"+sample_basename+"_contigs.fasta")
                    
    # MLST call
    print("\nStep 6: MLST\n")
    mlst_call(input_dir=output_folder+"/"+contigs_dir,
            output_dir=output_folder+"/"+mlst_dir,
            output_filename="MLST.txt")
    
    # ABRicate call (virulence genes)
    print("\nStep 7: ABRicate (virulence genes)\n")
    abricate_call(input_dir=output_folder+"/"+contigs_dir,
                 output_dir=output_folder+"/"+abricate_vir_dir,
                 output_filename="SampleVirulenceGenes.tab",
                 database = "vfdb")

    # ABRicate call (antibiotic resistance genes)
    print("\nStep 8: ABRicate (antibiotic resistance genes)\n")
    abricate_call(input_dir=output_folder+"/"+contigs_dir,
                 output_dir=output_folder+"/"+abricate_abr_dir,
                 output_filename="SampleAntibioticResistanceGenes.tab",
                 database = "resfinder")
                 
    # Roary call
    print("\nStep 9: Roary\n")
    roary_call()
