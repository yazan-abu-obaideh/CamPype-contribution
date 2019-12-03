import pandas as pd
import datetime
import os
import shutil
import logging
import sys
import workflow_config as cfg
from terminal_banner import Banner
from subprocess import call
from Bio import SeqIO


def read_aux_files(inputfile):
    """
    File containing auxiliary files routes.
    
    Arguments:
        inputfile {string} -- Filename (and route) of the file containing inputs.
    
    Returns:
        files_routes {tuple} -- Tuple of auxiliary files (adapters, reference_annotation_file, protein_reference). I return it like this to avoid length missmatches.
    """
    files_df = pd.read_csv(inputfile, sep="\t")
    files_routes = []
    for _, row in files_df.iterrows():
        files_routes.append(row["Route"])
    return files_routes[0], files_routes[1], files_routes[2] 


def read_input_files(indexfile):
    """
    Gets every pair of reads on input_files.csv
    
    Arguments:
        indexfile {string} -- Filename (and route) of the file containing inputs.
    
    Returns:
        files_tuples {list of tuples} -- List of tuples each containing forward read file path, reverse read file path and file basename (just the sample number).
    """
    files_df = pd.read_csv(indexfile, sep="\t")
    files_tuples = []
    for _, row in files_df.iterrows():
        files_tuples.append((row["Read1"], row["Read2"], str(row["Samples"])))

    return files_tuples


def trimmomatic_call(input_file1, input_file2, phred, trimfile,
                    paired_out_file1, paired_out_file2, unpaired_out_file1, unpaired_out_file2):
    """
    Trimmomatic call.
    
    Arguments:
        input_file1 {string} -- Input file forward (and route).
        input_file2 {string} -- Input file reverse (and route).
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
        input_file1 {string} -- Input file forward (and route).
        input_file2 {string} -- Input file reverse (and route).
    
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
    for root, _dirs, files in os.walk(input_dir):
        main_out_folder = root.split("/")[0]
        for filename in files:
            if filename.__contains__("prinseq"):
                if filename.__contains__("singletons"):
                    os.remove(os.path.join(root, filename))
                else:
                    # Move every prinseq file from trimmomatic folder to prinseq folder
                    shutil.move(os.path.join(root, filename), output_dir+"/"+sample)
                    if filename.startswith(sample+"_R1"):
                        filenames["R1"] = filename
                    elif filename.startswith(sample+"_R2"):
                        filenames["R2"] = filename
    return filenames


def spades_call(forward_sample, reverse_sample, sample, out_dir):
    """
    Spades call
    
    Arguments:
        forward_sample {string} -- Forward sample file name (and route).
        reverse_sample {string} -- Reverse sample file name (and route).
        sample {string} -- Sample basename.
        out_dir {string} -- Output directory.
    
    Returns:
        {int} -- Execution state (0 if everything is all right)
    """
    arguments = ["spades.py", "-1", forward_sample, "-2", reverse_sample, "--careful", "--cov-cutoff", "auto", "-o", out_dir+"/"+sample]    
    return call(arguments)


def contigs_trim_and_rename(contigs_file, output_dir, min_len):
    """
    Creates new fasta file filtering sequences shorter than min_len and shortening sequence identifiers.
    
    Arguments:
        contigs_file {string} -- Original contigs filename (and route).
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
        input_file {string} -- Input file (and route).
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
        output_filename {string} -- Output file name (and route).
    
    Returns:
        {int} -- Execution state (0 if everything is all right)
    """
    output_file = open(output_dir+"/"+output_filename, "w")
    
    input_filenames = []

    for _root, _dirs, files in os.walk(input_dir):
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
        output_filename {string} -- Output file name (and route).
        database {string} -- Database name.
    
    Returns:
        {int} -- Execution state (0 if everything is all right)
    """
    output_file = open(output_dir+"/"+output_filename, "w")
    
    input_filenames = []

    for _root, _dirs, files in os.walk(input_dir):
        for filename in files:
            if filename.endswith(".fasta"):
                input_filenames.append(input_dir+"/"+filename)

    arguments = ["abricate", *input_filenames, "--db", database]
    return call(arguments, stdout=output_file)


def blast_call(proteins_file_ori, proteins_file_dest, contigs_files_paths, blast_database_output, blast_output_folder, blast_output_name):
    """
    Blast call.
    
    Arguments:
        proteins_file_ori {string} -- Reference proteins file path (origin).
        proteins_file_dest {string} -- Reference proteins file path (destination).
        contigs_files_paths {list} -- List of contig files from SPAdes.
        blast_database_output {string} -- Destination folder to blast database.
        blast_output_folder {string} -- Destination folder to blast output.
        blast_output_name {string} -- Output file name.
    
    Returns:
        {int} -- Execution state (0 if everything is all right)
    """
    # Move VF_custom.txt to ABRicateVirulenceGenes/BLAST_custom_proteins
    shutil.copy(proteins_file_ori, proteins_file_dest)

    # Concat every contig from SPAdes on DNA_database.fna (replacing sequences names)
    with open(blast_database_output, "w") as output_file:
        for contig_file_path in contigs_files_paths:
            for record in SeqIO.parse(contig_file_path, "fasta"):
                strain = contig_file_path.split("/")[-2]
                record.id = record.name = record.description = strain+"_N_"+"_".join(record.id.split("_")[1:])
                SeqIO.write(record, output_file, "fasta")
                
    # Create blast database
    blast_db_path = os.path.dirname(os.path.abspath(blast_database_output))+"/DNA_database"
    call(["makeblastdb", "-in", blast_database_output, "-dbtype", "nucl", 
          "-out", blast_db_path, "-title", "DNA_Database"])

    # Call tblastn
    tblastn_state = call(["tblastn", "-db", blast_db_path, "-query", proteins_file_dest, "-evalue", "10e-4", "-outfmt", 
                        "6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore sseq", 
                        "-out", blast_output_folder+"/"+blast_output_name])

    # Add header to tblastn output
    with open(blast_output_folder+"/"+blast_output_name, 'r+') as f:
        content = f.read()
        f.seek(0, 0)
        headers = ["query id", "subject id", "% identity", "alignment length", "mismatches", "gap opens", 
                   "query start", "query end", "subject start", "subject end", "evalue", "score", "aligned part of subject sequence"]

        f.write("\t".join(headers) + '\n' + content)

    return tblastn_state


def prokka_call(locus_tag, output_dir, prefix, input_file):
    """
    Prokka call.
    
    Arguments:
        locus_tag {string} -- Locus tag prefix.
        output_dir {string} -- Output directory.
        prefix {string} -- Filename output prefix.
        input_file {string} -- Input filename (and route).
    
    Returns:
        {int} -- Execution state (0 if everything is all right)
    """
    arguments = ["prokka", "--locustag", locus_tag, "--outdir", output_dir, "--prefix", prefix, "--kingdom", "Bacteria", "--gcode", "11", input_file]
    return call(arguments)


def dfast_call(input_file, min_length, out_path, sample_basename):
    """
    Dfast call.
    
    Arguments:
        input_file {string} -- Input filename (and route).
        min_length {int} -- Minimum sequence length.
        out_path {strin} -- Output folder.
    
    Returns:
        {int} -- Execution state (0 if everything is all right)
    """
    arguments = ["dfast", "--genome", input_file, "--minimum_length", str(min_length), "--out", out_path]
    state = call(arguments)

    # Replace default output filenames including string basename
    for root, _dirs, files in os.walk(out_path):
        for filename in files:
            if filename.__contains__("genome"):
                new_filename = filename.replace("genome", sample_basename)
                shutil.move(os.path.join(root, filename), os.path.join(root, new_filename))

    return state


def roary_call(input_files, output_dir):
    """
    Roary call.
    
    Arguments:
        input_files {list} -- GFF files from prokka.
        output_dir {string} -- Output directory.
    
    Returns:
        {int} -- Execution state (0 if everything is all right)
    """
    arguments = ["roary", "-f", output_dir, *input_files]
    ex_state = call(arguments)
    # Set Roary output directory name
    for _root, dirs, _files in os.walk("."):
        for dirname in dirs:
            if dirname.startswith("Roary_pangenome_"):
                os.rename(dirname, "Roary_pangenome")
    return ex_state


def roary_plots_call(input_newick, input_gene_presence_absence, output_dir):
    """
    Roary plots call
    
    Arguments:
        input_newick {string} -- Filename (and route) to newick input file.
        input_gene_presence_absence {[type]} -- Filename (and route) to gene presence/absence input file.
        output_dir {[type]} -- Route to output files.
    
    Returns:
        {int} -- Execution state (0 if everything is all right)
    """
    arguments = ["python", "utils/roary_plots.py", input_newick, input_gene_presence_absence]
    ex_state = call(arguments)
    
    # Roary_plots saves output files in the current directory, so we move them to our own
    for root, _dirs, files in os.walk("."):
        for filename in files:
            if filename.startswith("pangenome_"):
                shutil.move(root+"/"+filename, output_dir+"/"+filename)
    return ex_state



def blast_postprocessing(blast_file, database_file, output_folder):
    """
    Blast post processing.
    
    Arguments:
        blast_file {string} -- Blast output file.
        database_file {string} -- Proteins database file.
        output_folder {string} -- Output folder.
    """
    
    # Read blast file as dataframe
    blast_output = pd.read_csv(blast_file, sep="\t")

    # Remove low identity rows 
    blast_output = blast_output[blast_output["% identity"] > 50]

    # Add query length and protein cover % columns
    blast_output.insert(2, "query length", "")
    blast_output.insert(3, "protein cover %", "")
    
    # Parse fasta database into dict
    proteins_database = {}
    for record in SeqIO.parse(database_file, "fasta"):
        proteins_database[record.id] = (record.description, record.seq)
    
    # Fill query length and protein cover % columns
    for index, row in blast_output.iterrows():
        query_id = row["query id"]
        query_length = len(proteins_database[query_id][1])
        blast_output.at[index, "query length"] = query_length

        # (query end - query start + 1) / query length * 100
        query_end = row["query end"]
        query_start = row["query start"]
        protein_cover = (query_end - query_start + 1) / query_length * 100
        blast_output.at[index, "protein cover %"] = protein_cover

    blast_output.to_csv(output_folder+"/BLASToutput_VF_custom_edited.txt", sep="\t",index=False)


if __name__ == "__main__":

    # Get config file parameters
    annotator = cfg.config["annotator"]
    run_blast = cfg.config["run_blast"]

    # Create output directories
    now = datetime.datetime.now()

    adapters_file, reference_annotation_file, proteins_file = read_aux_files("reference_files.csv")
    
    output_folder = sys.argv[1]
    trimmomatic_dir = output_folder+"/Trimmomatic_filtering1"
    prinseq_dir = output_folder+"/Prinseq_filtering2"
    spades_dir = output_folder+"/SPAdes_assembly"
    contigs_dir = output_folder+"/Contigs_renamed_shorten"
    mlst_dir = output_folder+"/MLST"
    abricate_vir_dir = output_folder+"/ABRicateVirulenceGenes"
    abricate_abr_dir = output_folder+"/ABRicateAntibioticResistanceGenes"
    prokka_dir = output_folder+"/Prokka_annotation"
    dfast_dir = output_folder+"/Dfast_annotation"
    roary_dir = output_folder+"/Roary_pangenome"
    roary_plots_dir = roary_dir+"/Roary_plots"
    blast_proteins_dir = abricate_vir_dir+"/BLAST_custom_proteins"
    dna_database_blast = blast_proteins_dir+"/DNA_database"

    if not os.path.exists(output_folder):
        os.mkdir(output_folder)
    
    os.mkdir(trimmomatic_dir)
    os.mkdir(prinseq_dir)
    os.mkdir(spades_dir)
    os.mkdir(contigs_dir)
    os.mkdir(mlst_dir)
    os.mkdir(abricate_vir_dir)
    os.mkdir(abricate_abr_dir)
    os.mkdir(blast_proteins_dir)
    os.mkdir(dna_database_blast)

    if annotator == "dfast":
        os.mkdir(dfast_dir)
    else:
        os.mkdir(prokka_dir)

    roary_input_files = []
    for sample1, sample2, sample_basename in read_input_files("input_files.csv"):
        # Trimmomatic call
        print(Banner("\nStep 1 for sequence "+sample_basename+": Trimmomatic\n"), flush=True)
        trimmomatic_call(input_file1=sample1,
                        input_file2=sample2,
                        phred="-phred33",
                        trimfile="ILLUMINACLIP:"+adapters_file+":1:30:11",
                        paired_out_file1=trimmomatic_dir+"/"+sample_basename+"_R1_paired.fastq",
                        unpaired_out_file1=trimmomatic_dir+"/"+sample_basename+"_R1_unpaired.fastq",
                        paired_out_file2=trimmomatic_dir+"/"+sample_basename+"_R2_paired.fastq",
                        unpaired_out_file2=trimmomatic_dir+"/"+sample_basename+"_R2_unpaired.fastq")

        # Create prinseq output directories
        os.mkdir(prinseq_dir+"/"+sample_basename)

        # Prinseq call
        print(Banner("\nStep 2 for sequence "+sample_basename+": Prinseq\n"), flush=True)
        prinseq_call(input_file1=trimmomatic_dir+"/"+sample_basename+"_R1_paired.fastq",
                    input_file2=trimmomatic_dir+"/"+sample_basename+"_R2_paired.fastq", 
                    min_len="40", 
                    min_qual_mean="25", 
                    trim_qual_right="25", 
                    trim_qual_window="15", 
                    trim_qual_type="mean",
                    out_format="3",
                    log_name=prinseq_dir+"/"+sample_basename+"/"+sample_basename+".log")

        # Prinseq output files refactor
        prinseq_files = refactor_prinseq_output(trimmomatic_dir, prinseq_dir, sample_basename)
        
        # Create SPAdes output directories
        os.mkdir(spades_dir+"/"+sample_basename)

        # SPAdes call
        print(Banner("\nStep 3 for sequence "+sample_basename+": SPAdes\n"), flush=True)
        spades_call(forward_sample=prinseq_dir+"/"+sample_basename+"/"+prinseq_files["R1"],
                    reverse_sample=prinseq_dir+"/"+sample_basename+"/"+prinseq_files["R2"],
                    sample=sample_basename,
                    out_dir=spades_dir)

        # Trim short contigs and shorten sequences id
        contigs_trim_and_rename(spades_dir+"/"+sample_basename+"/"+"contigs.fasta", 
                                contigs_dir+"/"+sample_basename+"_contigs.fasta",
                                500)    # TODO Para el futuro, este valor deberá ser el doble de la longitud de una read del archivo .fastq del secuenciador

        # Create Quast output directories
        quast_dir = sample_basename+"_assembly_statistics"
        os.mkdir(spades_dir+"/"+sample_basename+"/"+quast_dir)

        # Quast call
        print(Banner("\nStep 4 for sequence "+sample_basename+": Quast\n"), flush=True)
        quast_call( input_file=contigs_dir+"/"+sample_basename+"_contigs.fasta",
                    output_dir=spades_dir+"/"+sample_basename+"/"+quast_dir,
                    min_contig=200)

        # Annotation (Prokka or dfast)
        if annotator.lower() == "dfast":
            # Dfast call
            annotation_dir = dfast_dir
            print(Banner("\nStep 5 for sequence "+sample_basename+": Dfast\n"), flush=True)
            dfast_call(input_file=contigs_dir+"/"+sample_basename+"_contigs.fasta",
                       min_length=0,
                       out_path=dfast_dir+"/"+sample_basename,
                       sample_basename=sample_basename)
        else:
            # Prokka call
            annotation_dir = prokka_dir
            print(Banner("\nStep 5 for sequence "+sample_basename+": Prokka\n"), flush=True)
            prokka_call(locus_tag=sample_basename+"_L",
                        output_dir=prokka_dir+"/"+sample_basename,
                        prefix=sample_basename,
                        input_file=contigs_dir+"/"+sample_basename+"_contigs.fasta")

        # Set roary input files
        roary_input_files.append(annotation_dir+"/"+sample_basename+"/"+sample_basename+".gff")

    # Annotate reference fasta file 
    if reference_annotation_file:
        reference_annotation_filename = reference_annotation_file.split("/")[-1]
        reference_annotation_basename = reference_annotation_filename.split(".")[-2]
        if annotator.lower() == "dfast":
            # Dfast call
            annotation_dir = dfast_dir
            print(Banner("\nStep 5 for reference sequence: Dfast\n"), flush=True)
            dfast_call(input_file=reference_annotation_file,
                        min_length=0,
                        out_path=dfast_dir+"/"+reference_annotation_basename,
                        sample_basename=reference_annotation_basename)
        else:
            # Prokka call
            annotation_dir = prokka_dir
            print(Banner("\nStep 5 for reference sequence: Prokka\n"), flush=True)
            prokka_call(locus_tag=reference_annotation_basename+"_L",
                        output_dir=prokka_dir+"/"+reference_annotation_basename,
                        prefix=reference_annotation_basename,
                        input_file=reference_annotation_file)

        # Set roary input files
        roary_input_files.append(annotation_dir+"/"+reference_annotation_basename+"/"+reference_annotation_basename+".gff")

    # MLST call
    print(Banner("\nStep 6: MLST\n"), flush=True)
    mlst_call(input_dir=contigs_dir,
            output_dir=mlst_dir,
            output_filename="MLST.txt")

    # ABRicate call (virulence genes)
    print(Banner("\nStep 7: ABRicate (virulence genes)\n"), flush=True)
    abricate_call(input_dir=contigs_dir,
                output_dir=abricate_vir_dir,
                output_filename="SampleVirulenceGenes.tab",
                database = "vfdb")

    # ABRicate call (antibiotic resistance genes)
    print(Banner("\nStep 8: ABRicate (antibiotic resistance genes)\n"), flush=True)
    abricate_call(input_dir=contigs_dir,
                output_dir=abricate_abr_dir,
                output_filename="SampleAntibioticResistanceGenes.tab",
                database = "resfinder")

    # Blast call
    print(Banner("\nStep 9: Blast\n"), flush=True)
    contig_files = [spades_dir+"/"+strainfolder+"/contigs.fasta" for strainfolder in os.listdir(spades_dir)]
    proteins_database_name = "VF_custom.txt"
    blast_output_name = "BLASToutput_VS_custom.txt"
    blast_call( proteins_file_ori=proteins_file, 
                proteins_file_dest=blast_proteins_dir+"/"+proteins_database_name, 
                contigs_files_paths=contig_files, 
                blast_database_output=dna_database_blast+"/DNA_database.fna", 
                blast_output_folder=blast_proteins_dir,
                blast_output_name=blast_output_name)
    blast_postprocessing(blast_file=blast_proteins_dir+"/"+blast_output_name,
                        database_file=blast_proteins_dir+"/"+proteins_database_name,
                        output_folder=blast_proteins_dir)

    # Roary call
    print(Banner("\nStep 10: Roary\n"), flush=True)
    roary_call(input_files=roary_input_files, output_dir=roary_dir)

    # Roary plots call
    os.mkdir(roary_plots_dir)
    print(Banner("\nStep 11: Roary Plots\n"), flush=True)
    roary_plots_call(input_newick=roary_dir+"/accessory_binary_genes.fa.newick",
                    input_gene_presence_absence=roary_dir+"/gene_presence_absence.csv",
                    output_dir=roary_plots_dir)

    print(Banner("\nDONE\n"), flush=True)