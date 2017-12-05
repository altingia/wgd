#!/usr/bin/python3.5
"""
Arthur Zwaenepoel - 2017

Alignment related tools.

Contribution note: It is trivial to add support for another aligner (besides MUSCLE and PRANK).
To add another aligner, only the :py:meth:`MSA.run_aligner` method should be modified to include
the aligner of interest.
"""
from .utils import read_fasta
import os
import subprocess
import warnings


def _nucleotide_msa_from_protein_msa(protein_msa_sequences, nucleotide_sequences):
    """
    Make a nucleotide multiple sequence alignment from a protein multiple sequence alignment

    :param protein_msa_sequences: dictionary with protein sequences (aligned)
    :param nucleotide_sequences: dictionary with nucleotide sequences (unaligned)
    :return: dictionary with nucleotide sequences (aligned)
    """
    nucleotide_msa = {}
    lengths = set()

    for seq in protein_msa_sequences.values():
        length = len(seq)
        lengths.add(length)

    if len(list(lengths)) != 1:
        warnings.warn("Not all sequences have the same length after alignment!")
        return None

    for gene_ID in protein_msa_sequences.keys():
        protein = protein_msa_sequences[gene_ID]
        if gene_ID not in nucleotide_sequences.keys():
            warnings.warn("Gene {} not found in nucleotide fasta!".format(gene_ID))
        else:
            nucleotide = nucleotide_sequences[gene_ID]
            nucleotide_msa_sequence = ''
            j = 0
            for i in range(len(protein)):
                if protein[i] == '-':
                    nucleotide_msa_sequence += '---'
                else:
                    nucleotide_msa_sequence += nucleotide[j:j+3]
                    j += 3
            nucleotide_msa[gene_ID] = nucleotide_msa_sequence

    return nucleotide_msa


def _strip_gaps(msa_dict):
    """
    Strip gap positions from a multiple sequence alignment (MSA).
    Finds the positions in the strings that have a gap and removes them in all sequences.

    :param msa_dict: dictionary with aligned nucleotide sequences.
    """
    if msa_dict is None:
        return None
    if len(list(msa_dict.values())) == 0:
        return None

    indices = set()
    length = len(list(msa_dict.values())[0])
    for i in range(length):
        for gene_ID in msa_dict.keys():
            # Prevent index error, raise warning instead
            if i >= len(msa_dict[gene_ID]):
                warnings.warn("Seems there are unequal string lengths after alignment in "
                              "this gene family. Occurred at gene: {}.".format(gene_ID))
                return None
            if msa_dict[gene_ID][i] == '-':
                indices.add(i)
    indices = list(indices)

    for gene_ID in msa_dict.keys():
        sequence_list = [i for i in msa_dict[gene_ID]]
        for index in sorted(indices, reverse=True):
            del sequence_list[index]
        msa_dict[gene_ID] = ''.join(sequence_list)

    return msa_dict


def multiple_sequence_aligment_nucleotide(msa_protein, nucleotide_sequences, min_length=100):
    """
    Make a nucleotide multiple sequence alignment based on a protein alignment

    :param msa_protein: dictionary of aligned protein sequences
    :return: nucleotide MSA, length, stripped length
    """
    if not os.path.isfile(msa_protein):
        warnings.warn('MSA file {} not found!'.format(msa_protein))
        return None

    protein_msa_sequences = read_fasta(msa_protein)
    nucleotide_msa = _nucleotide_msa_from_protein_msa(protein_msa_sequences, nucleotide_sequences)

    if nucleotide_msa is None:
        return None

    # get alignment statistics for quality control
    alignment_stats = pairwise_alignment_stats(nucleotide_msa)
    l = len(list(nucleotide_msa.values())[0])

    # strip gaps
    nucleotide_msa = _strip_gaps(nucleotide_msa)

    if nucleotide_msa is None:  # probably not necessary
        return None

    elif len(list(nucleotide_msa.values())[0]) < min_length:
        return None

    l_stripped = len(list(nucleotide_msa.values())[0])

    msa_nuc = msa_protein + '.nuc'
    with open(msa_nuc, 'w') as o:
        o.write("\t{0}\t{1}\n".format(len(nucleotide_msa.keys()), len(list(nucleotide_msa.values())[0])))
        for gene_ID in nucleotide_msa.keys():
            o.write("{}\n".format(gene_ID))
            o.write(nucleotide_msa[gene_ID])
            o.write("\n")

    return [msa_nuc, int(l), int(l_stripped), alignment_stats]


def pairwise_alignment_stats(msa):
    """
    Get pairwise stats from MSA.
    Return as  dictionary {Gene1: {Gene2: [0.8, 0.7], Gene3: [...], ...}

    :param msa: MSA dictionary
    :return: dictionary
    """
    stats = {}
    seqs = [(x, msa[x]) for x in sorted(msa.keys())]

    for i in range(len(seqs)):
        stats[seqs[i][0]] = {}
        for j in range(i, len(seqs)):
            id1, id2 = seqs[i][0], seqs[j][0]
            d = _strip_gaps({id1: seqs[i][1], id2: seqs[j][1]})
            try:
                # % identity
                stats[id1][id2] = [(len(d[id1]) - hamming_distance(d[id1], d[id2]))/len(d[id1])]
                # coverage
                stats[id1][id2].append(len(d[id1])/len(seqs[i][1]))
            except:
                stats[id1][id2] = [0, 0]
    return stats


def hamming_distance(s1, s2):
    """Return the Hamming distance between equal-length sequences"""
    if len(s1) != len(s2):
        raise ValueError("Undefined for sequences of unequal length")
    return sum(el1 != el2 for el1, el2 in zip(s1, s2))


class MSA:
    """
    Multiple multiple sequence alignment (MSA) programs python wrappers.
    Currently only runs with default settings.

    :param muscle: path to Muscle executable, will by defult look for Muscle/PRANK in the system PATH
    :param tmp: directory to store temporary files.

    Usage examples

    * Sequences in dictionary, output as dictionary::

        >>> sequences = {'bear_gene': 'BEAR', 'hare_gene': 'HARE', 'yeast_gene': 'BEER'}
        >>> msa = MSA()
        >>> msa.run_aligner(sequences)

    * Sequences in fasta file, output as fasta file ``(msa.fasta)``::

        >>> msa = MSA()
        >>> msa.run_aligner('./sequences.fasta', './msa.fasta')

    """

    def __init__(self, muscle='muscle', prank='prank', tmp='./tmp'):
        """
        Muscle wrapper init.

        :param muscle: path to Muscle executable, will by defult look for Muscle in the system PATH
        :param prank: path to PRANK executable
        :param tmp: directory to store temporary files.
        """
        self.muscle = muscle
        self.prank = prank
        self.tmp = tmp

        if not os.path.isdir(self.tmp):
            raise NotADirectoryError('tmp directory {} not found!'.format(self.tmp))

    def run_aligner(self, sequences, aligner='muscle', file=None):
        """
        Run MSA on sequences stored in dictionary with a particular aligner

        :param sequences: dictionary of sequences or input fasta file
        :param file: output file name, if not provided output is dictionary
        :param aligner: alignment software to use (prank|muscle)
        :return: MSA file
        """
        if not file:
            file_name = 'msa'
        else:
            file_name = file

        # sequences provided in dictionary
        if type(sequences) == dict:
            target_path_fasta = os.path.join(self.tmp, '{}.fasta'.format(file_name))

            with open(target_path_fasta, 'w') as o:
                for gene in sequences.keys():
                    o.write('>{}\n'.format(gene))
                    o.write(sequences[gene])
                    o.write('\n')

        # sequences provided as fasta file
        elif os.path.isfile(sequences):
            target_path_fasta = sequences

        # error
        else:
            raise FileNotFoundError('{} is not a dictionary and also not a file path'.format(sequences))

        target_path_msa = os.path.join(self.tmp, '{}.msa'.format(file_name))

        if aligner == 'muscle':
            subprocess.run([self.muscle, '-quiet', '-in', target_path_fasta, '-out', target_path_msa],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        elif aligner == 'prank':
            subprocess.run([self.prank, '-d=' + target_path_fasta, '-o=' + target_path_msa],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            subprocess.run(['mv', '{}.best.fas'.format(target_path_msa), target_path_msa])

        subprocess.run(['rm', target_path_fasta], stdout=subprocess.PIPE)

        if not file:
            out = read_fasta(target_path_msa)
            return out

        return target_path_msa