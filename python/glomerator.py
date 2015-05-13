import itertools
import os
import sys
import math
import csv
from sklearn.metrics.cluster import adjusted_mutual_info_score

import utils
from opener import opener
from clusterpath import ClusterPath

# ----------------------------------------------------------------------------------------
class Glomerator(object):
    # ----------------------------------------------------------------------------------------
    def __init__(self, reco_info=None):
        self.reco_info = reco_info
        self.paths = None

    # ----------------------------------------------------------------------------------------
    def naive_seq_glomerate(self, naive_seqs, n_clusters, debug=False):
        """ Perform hierarchical agglomeration (with naive hamming distance as the distance), stopping at <n_clusters> """
        clusters = [[names,] for names in naive_seqs.keys()]
        # for seq_a, seq_b in itertools.combinations(naive_seqs.values(), 2):
        #     if len(seq_a) != len(seq_b):
        #         print '  different lengths'
        #         continue
        #     print seq_a, seq_b, utils.hamming(seq_a, seq_b)

        seqs_per_cluster = float(len(clusters)) / n_clusters
        min_per_cluster, max_per_cluster = int(math.floor(seqs_per_cluster)), int(math.ceil(seqs_per_cluster))

        distances = {}  # cache the calculated hamming distances (probably doesn't really make much of a difference)
        # completed_clusters = []  # clusters that are already big enough, i.e. we don't want to add anything else to 'em

        def glomerate():
            smallest_min_distance = None
            clusters_to_merge = None
            if debug:
                print '  current',
                for clust in clusters:
                    print ' %d' % len(clust),
                print ''
            for clust_a, clust_b in itertools.combinations(clusters, 2):
                # if clust_a in completed_clusters or clust_b in completed_clusters:
                #     continue
                if len(clust_a) + len(clust_b) > max_per_cluster and not glomerate.merge_whatever_you_got:  # merged cluster would be too big, so look for smaller (albeit further-apart) things to merge
                    if debug:
                        print '  skip', len(clust_a), len(clust_b)
                    continue
                min_distance = None  # find the smallest hamming distance between any two sequences in the two clusters
                for query_a in clust_a:
                    for query_b in clust_b:
                        joint_key = ';'.join(sorted([query_a, query_b]))
                        if joint_key not in distances:
                            distances[joint_key] = utils.hamming(naive_seqs[query_a], naive_seqs[query_b])
                        # if debug:
                        #     print '    %25s %25s   %4d   (%s)' % (query_a, query_b, distances[joint_key], joint_key)
                        if min_distance is None or distances[joint_key] < min_distance:
                            min_distance = distances[joint_key]
                if smallest_min_distance is None or min_distance < smallest_min_distance:
                    smallest_min_distance = min_distance
                    clusters_to_merge = (clust_a, clust_b)

            if clusters_to_merge is None:  # if we didn't find a suitable pair
                if debug:
                    print '    didn\'t find shiznitz'
                glomerate.merge_whatever_you_got = True  # next time through, merge whatever's best regardless of size
            else:
                if debug:
                    print '    merging', len(clusters_to_merge[0]), len(clusters_to_merge[1])
                clusters.append(clusters_to_merge[0] + clusters_to_merge[1])
                clusters.remove(clusters_to_merge[0])
                clusters.remove(clusters_to_merge[1])


            # if len(clusters[-1]) > max_per_cluster:
            #     if debug:
            #         print '  completed %s ' % clusters[-1]
            #     completed_clusters.append(clusters[-1])

        glomerate.merge_whatever_you_got = False  # merge the best pair, even if together they'll be to big

        while len(clusters) > n_clusters:
            glomerate()

        # roughly equalize the cluster sizes
        if len(clusters) > 1:
            # mean_length = sum([len(cl) for cl in clusters]) / float(len(clusters))
            clusters.sort(key=len)

            def homogenize():
                if debug:
                    print 'before',
                    for cl in clusters:
                        print len(cl),
                    print ''
                if len(clusters) > 2:
                    clusters[0] = clusters[0] + clusters[1]
                    clusters[1] = clusters[-1][ : len(clusters[-1])/2]
                    clusters[-1] = clusters[-1][len(clusters[-1])/2 : ]
                else:  # only two clusters
                    together = clusters[0] + clusters[1]
                    clusters[0] = together[ : len(together)/2]
                    clusters[1] = together[len(together)/2 : ]
                if debug:
                    print 'after',
                    for cl in clusters:
                        print len(cl),
                    print ''
                clusters.sort(key=len)

            itries = 0
            while len(clusters[0]) < len(clusters[-1]) / 1.5:
                if debug:
                    print '  homogenizing', len(clusters[0]), len(clusters[-1])  #, len(clusters[-1]) / 3.
                homogenize()
                itries += 1
                if itries > 100:
                    break

        return clusters

    # # ----------------------------------------------------------------------------------------
    # def print_partitions(self, path, extrastr='', one_line=False):
    #     for ip in range(len(path.partitions)):
    #         self.print_partition(path.partitions[ip], path.logprobs[ip], path.adj_mis[ip], extrastr=extrastr, one_line=one_line)

    # # ----------------------------------------------------------------------------------------
    # def print_partition(self, partition, logprob, adj_mi=-1., extrastr='', one_line=False):
    #     if one_line:
    #         print '    %s %-15.2f   %-8.3f   %3d clusters (%d ways):' % (extrastr, logprob, adj_mi, len(partition), -1),  #1./math.exp(self.logweights[ip])),
    #     else:
    #         print '  %s partition   %-15.2f    %-8.2f' % (extrastr, logprob, adj_mi)
    #         print '   clonal?   ids'
    #     for cluster in partition:
    #         same_event = utils.from_same_event(self.reco_info is None, self.reco_info, cluster)
    #         if same_event is None:
    #             same_event = -1
    #         cluster_str = ':'.join([str(uid) for uid in cluster])
    #         if one_line:
    #             print '   %s' % cluster_str,
    #         else:
    #             print '     %d    %s' % (int(same_event), cluster_str)
    #     if one_line:
    #         print ''

    # ----------------------------------------------------------------------------------------
    def print_true_partition(self):
        print '  true partition'
        print '   clonal?   ids'
        true_partition = {}
        for key in self.reco_info:
            reco_id = self.reco_info[key]['reco_id']
            if reco_id not in true_partition:
                true_partition[reco_id] = []
            true_partition[reco_id].append(self.reco_info[key]['unique_id'])
        for cluster in true_partition.values():
            same_event = utils.from_same_event(self.reco_info is None, self.reco_info, cluster)
            if same_event is None:
                same_event = -1
            print '     %d    %s' % (int(same_event), ':'.join([str(uid) for uid in cluster]))

    # ----------------------------------------------------------------------------------------
    def mutual_information(self, partition, debug=False):
        if self.reco_info is None:
            return -1.0
        true_cluster_list, inferred_cluster_list = [], []
        for iclust in range(len(partition)):
            for uid in partition[iclust]:
                if uid not in self.reco_info:
                    raise Exception('ERROR %s' % str(uid))
                true_cluster_list.append(self.reco_info[uid]['reco_id'])
                inferred_cluster_list.append(iclust)
        adj_mi = adjusted_mutual_info_score(true_cluster_list, inferred_cluster_list)
        if debug:
            print '       true clusters %d' % len(set(true_cluster_list))
            print '   inferred clusters %d' % len(set(inferred_cluster_list))
            print '         adjusted mi %.2f' % adj_mi
        return adj_mi

    # ----------------------------------------------------------------------------------------
    def read_file_info(self, infname, n_paths):
        paths = [None for _ in range(n_paths)]
        with opener('r')(infname) as csvfile:
            reader = csv.DictReader(csvfile)
            for line in reader:
                if line['partition'] == '':
                    raise Exception('ERROR null partition (one of the processes probably got passed zero sequences')  # shouldn't happen any more FLW
                uids = []
                for cluster in line['partition'].split(';'):
                    uids.append([unique_id for unique_id in cluster.split(':')])
                path_index = int(line['path_index'])
                if paths[path_index] is None:
                    paths[path_index] = ClusterPath(int(line['initial_path_index']))
                else:
                    assert paths[path_index].initial_path_index == int(line['initial_path_index'])
                paths[path_index].add_partition(uids, float(line['score']), float(line['logweight']), self.mutual_information(uids, debug=False))

        for cp in paths:
            if cp is None:
                raise Exception('None type path read from %s' % infname)
            for ptn in cp.partitions:
                if len(ptn) == 0:
                    raise Exception('zero length partition read from %s' % infname)

        return paths

    # ----------------------------------------------------------------------------------------
    def merge_partitions(self, partitions, logprobs, logweights, adj_mis):
        pass

    # ----------------------------------------------------------------------------------------
    def merge_fileinfos(self, fileinfos, smc_particles, previous_info=None, debug=False):
        print 'TODO not doing the combined conservative thing any more seems to have knocked down performance a bit EDIT nevermind, that seems to be a result of smc (presumably it was choosing very unlikely merges)'
        self.paths = [ClusterPath(None) for _ in range(smc_particles)]  # each path's initial_path_index is None since we're merging paths that, in general, have different initial path indices

        if previous_info is not None:  # DEAR FUTURE SELF this won't make any sense until you find that picture you took of the white board
            assert len(previous_info) == len(fileinfos)  # both are the number of processes we're merging into one
            # TODO prevent this from adding duplicate adjacent partitions
            if debug:
                print 'prepend previous history'
            for ifile in range(len(fileinfos)):
                if debug:
                    print 'ifile', ifile
                for ipath in range(smc_particles):
                    if debug:
                        print '  ipath', ipath
                        print '    before'
                        fileinfos[ifile][ipath].print_partitions(self.reco_info, one_line=True)
                    initial_path_index = fileinfos[ifile][ipath].initial_path_index  # which previous path are we hooking up to?
                    previous_path = previous_info[ifile][initial_path_index]
                    current_path = fileinfos[ifile][ipath]
                    first_new_logprob = current_path.logprobs[0]
                    extended_path = ClusterPath(None)
                    for ip in range(len(previous_path.partitions)):
                        # if previous_path.logprobs[ip] >= first_new_logprob:  # skip the merges past which we rewound
                        #     continue
                        extended_path.add_partition(list(previous_path.partitions[ip]), previous_path.logprobs[ip], previous_path.logweights[ip], previous_path.adj_mis[ip])
                    for ip in range(len(current_path.partitions)):
                        extended_path.add_partition(list(current_path.partitions[ip]), current_path.logprobs[ip], current_path.logweights[ip], current_path.adj_mis[ip])
                    fileinfos[ifile][ipath] = extended_path
                    fileinfos[ifile][ipath].set_synthetic_logweight_history(self.reco_info)  # need to multiply the combinatorical factors in the later partitions by the factors from the earlier partitions
                    if debug:
                        print '    after'
                        fileinfos[ifile][ipath].print_partitions(self.reco_info, one_line=True)

        for ipath in range(smc_particles):

            if debug:
                print 'merge path %d from %d processes:' % (ipath, len(fileinfos))
                for ifile in range(len(fileinfos)):
                    fileinfos[ifile][ipath].print_partitions(self.reco_info, extrastr=('%d' % (ifile)), one_line=True)
                    print ''

            # merge all the steps in each path
            def last_one():
                last = True
                for ifile in range(len(fileinfos)):  # we're finished when all the files are out of glomeration steps (i.e. they all only have one [the last] line left)
                    last &= len(fileinfos[ifile][ipath].partitions) == 1
                return last

            def remove_one_of_the_first_partitions():
                maxdelta, ibestfile = None, None
                for ifile in range(len(fileinfos)):
                    if len(fileinfos[ifile][ipath].partitions) == 1:  # if this is the last line (i.e. there aren't any more glomeration steps in this file), leave it alone
                        continue
                    thisdelta = fileinfos[ifile][ipath].logprobs[1] - fileinfos[ifile][ipath].logprobs[0]  # logprob difference between the next partition and this one
                    if maxdelta is None or thisdelta > maxdelta:
                        maxdelta = thisdelta
                        ibestfile = ifile
                # print '    ibest %d with %f - %f = %f' % (ibestfile, fileinfos[ibestfile][ipath].logprobs[1], fileinfos[ibestfile][ipath].logprobs[0], fileinfos[ibestfile][ipath].logprobs[1] - fileinfos[ibestfile][ipath].logprobs[0])
                fileinfos[ibestfile][ipath].remove_first_partition()

            def add_next_global_partition():
                global_partition = []
                global_logprob = 0.
                for ifile in range(len(fileinfos)):  # combine the first line in each file to make a global partition
                    for cluster in fileinfos[ifile][ipath].partitions[0]:
                        global_partition.append(list(cluster))
                    global_logprob += fileinfos[ifile][ipath].logprobs[0]
                global_adj_mi = self.mutual_information(global_partition, debug=False)
                self.paths[ipath].add_partition(global_partition, global_logprob, 0., global_adj_mi)  # don't know the logweight yet (or maybe at all!)

            while not last_one():
                add_next_global_partition()
                remove_one_of_the_first_partitions()
            add_next_global_partition()

            self.paths[ipath].set_synthetic_logweight_history(self.reco_info)
            if debug:
                print '  merged path:'
                self.paths[ipath].print_partitions(self.reco_info, one_line=True)

    # ----------------------------------------------------------------------------------------
    def read_cached_agglomeration(self, infnames, smc_particles, previous_info=None, debug=False):
        """ Read the partitions output by bcrham. If <all_partitions> is specified, add the info to it """
        fileinfos = []
        for fname in infnames:
            fileinfos.append(self.read_file_info(fname, smc_particles))
        self.merge_fileinfos(fileinfos, smc_particles, previous_info=previous_info, debug=debug)

        return self.paths

    # ----------------------------------------------------------------------------------------
    def write_partitions(self, outfname, mode, paths):
        with open(outfname, mode) as outfile:
            writer = csv.DictWriter(outfile, ('path_index', 'score', 'logweight', 'adj_mi'))
            writer.writeheader()
            for ipath in range(len(paths)):
                for ipart in range(len(paths[ipath].partitions)):
                    writer.writerow({'path_index' : ipath,
                                     'score' : paths[ipath].logprobs[ipart],
                                     'logweight' : paths[ipath].logweights[ipart],
                                     # 'normalized_score' : part['score'] / self.max_log_probs[ipath],
                                     'adj_mi' : paths[ipath].adj_mis[ipart]})
