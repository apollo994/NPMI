#in piu rispetto a 2:
#   -calcolo delle medie di NPMI sia su famiglie intersezioni che significative
#   -insermimento delle medie nei risultati e paragrafo GENERAL RESULTS da cui estrarree nella valutazione del confronto

import sys
import time
import argparse
from collections import defaultdict
import re
import random
from collections import Counter
import math
from decimal import Decimal
#pachhetto per parlare con il sistema operativo
import os
#pacchetto per la statistica in python
import scipy
from scipy.stats import binom
from scipy.stats import hypergeom



def main():
    parser = argparse.ArgumentParser(description='Tool for normalised pointwise mutal information computation across two DE gene list')
    parser.add_argument('--plaza', metavar='plaza',help='the table from plaza with all family, species and genes')
    parser.add_argument('--sp1', metavar='sp1',help='species 1, es. ath,sly,osa,hvu')
    parser.add_argument('--sp2', metavar='sp2',help='species 2, es. ath,sly,osa,hvu')
    parser.add_argument('--in_sp1', metavar='in_sp1', help='The significant plazaID of species 1')
    parser.add_argument('--in_sp2', metavar='in_sp2', help='The significant plazaID of species 2')
    #otional
    parser.add_argument('--th_sc', metavar='th_sc',type=float ,default="0.05" ,help='Threshold for direct ortgologs enrichment (def=0.05)')
    parser.add_argument('--random', metavar='random',type=int ,default="10000" ,help='number of list of random plazaID to generate (def=10000)')
    parser.add_argument('--FDR', metavar='FDR',default="BY" ,help='Type of multiple test correction, BH or BY (def=BY)')
    parser.add_argument('--th', metavar='th',type=float ,default="0.05" ,help='BY correction threshold (def=0.05)')
    parser.add_argument('--sample', metavar='sample', default="my_sample_result", help='sample name')

    args = parser.parse_args()

################################################################################

    #funzione per creare cartelle se non ancora esistenti
    def createFolder(directory):
        try:
            if not os.path.exists(directory):
                os.makedirs(directory)
        except OSError:
            print ('Error: Creating directory. ' +  directory)
            sys.exit(1)

    #creo la cartella dove salvare i risultati

    createFolder("./"+args.sample+"_results/")

    #salvo in una stringa il nome dei due campioni partendo da file di input
    sample_sp1=args.in_sp1.split("/")
    sample_sp1=sample_sp1[len(sample_sp1)-1]

    sample_sp2=args.in_sp2.split("/")
    sample_sp2=sample_sp2[len(sample_sp2)-1]

################################################################################

    #funzione per trovare intersezione tra due liste

    def common_elements(list1, list2):
        return list(set(list1) & set(list2))

################################################################################

    #funzione per calcolare le volte che vedo una famiglia nel set analizzato

    def compute_count_list(plazaID_list):
        plazaID_freq=dict(Counter(plazaID_list))

        return plazaID_freq

################################################################################

    #funzione per barra di caricamento

    def update_progress(job_title, progress):
        length = 20 # lunghezza barra
        block = int(round(length*progress))
        msg = "\r{0}: [{1}] {2}%".format(job_title, "#"*block + "-"*(length-block), round(progress*100, 1))
        if progress >= 1: msg += " DONE\r\n"
        sys.stdout.write(msg)
        sys.stdout.flush()

################################################################################

    #funzione per calcolare la npmi

    def compute_npmi(p_my,p_all):
        npmi= (math.log(p_my/p_all, 2.0))/(-(math.log(p_all,2.0)))

        return npmi

################################################################################

    #funzione per calcolare 1-distribuzione ipergeometrica CUMULATIVA
    #ATTENZIONE, ordine non canonico (excel) per passaggio parametri

    def hyp_dist(successi,popolazione,succeccessi_popolazione,tentativi):
        x=successi
        M=popolazione
        n=succeccessi_popolazione
        N=tentativi

        return round(1-hypergeom.cdf(x, M, n, N),12)


################################################################################

    #funzione per calcolare 1 - distribuzione binomiale cumulativa

    def bin_dist(n_obs,n_my_gene,p_all):
        k=n_obs-1
        n=n_my_gene
        p=p_all

        return round(1-binom.cdf(k,n,p),6)

################################################################################

    #funzione per ottenere gli elementi unici di una lista

    def unique(list1):
        return(list(set(list1)))

################################################################################

    #funzione per calcolare FDR con metodo BH

    def BH_FDR(serie):
        #indice per ciclare sui valori al contrario
        index=sorted(list(range(0,len(serie))), reverse=True)
        #lista in cui annotare i risultari
        BH_res=[]
        #numero di test
        n=len(serie)
        #variabili per controllare se il pv è uguale al precedente o FDR diventa piu piccolo del precedente
        ex_pv=1
        ex_adj_pv=1
        for idx in index:
            #aggiungo 1 all'indice che parte da 0 per ottenere il rank
            rank=idx+1
            #annoto il pv
            pv=serie[idx]
            #se il pv analizzato è uguale al pv precedente annoto il pv corretto come il precedente
            if pv==ex_pv:
                adj_pv=ex_adj_pv
                BH_res.append(adj_pv)
            #se invece il pv è piu basso del precedente aggiiorno ex_pv e calcolo il nuovo pv corretto
            if pv<ex_pv:
                ex_pv=pv
                #calcolo il il pv corretto
                adj_pv=pv*(n/rank)
                #verifico se adj_pv è piu piccolo del precedente
                if adj_pv<ex_adj_pv:
                    #annoto il pv corretto nella lista e nell ex_BH
                    ex_adj_pv=adj_pv
                    BH_res.append(adj_pv)
                #se non lo è uso il precedente
                else:
                    adj_pv=ex_adj_pv
                    BH_res.append(ex_adj_pv)


        #riordino la lista dei risultati in ordine crescente
        BH_res=sorted(BH_res)

        return (BH_res)

################################################################################

    #funzione per calcolare FDR con metodo BY

    def BY_FDR(serie):
        #indice per ciclare sui valori al contrario
        index=sorted(list(range(0,len(serie))), reverse=True)
        #lista in cui annotare i risultari
        BY_res=[]
        #numero di test
        n=len(serie)
        #variabili per controllare se il pv è uguale al precedente o FDR diventa piu piccolo del precedente
        ex_pv=1
        ex_adj_pv=1
        #calcolo il valore q (sommatoria di 1/rank) dell'ultima posizione da cui po sottraggo ogni volta
        q=0
        #print(q)
        for i in index:
            rank=(i+1)
            q=q+1/rank


        for idx in index:
            #aggiungo 1 all'indice che parte da 0 per ottenere il rank
            rank=idx+1
            #annoto il pv
            pv=serie[idx]
            #se il pv analizzato è uguale al pv precedente annoto il pv corretto come il precedente
            if pv==ex_pv:
                adj_pv=ex_adj_pv
                BY_res.append(adj_pv)
            #se invece il pv è piu basso del precedente aggiiorno ex_pv e calcolo il nuovo pv corretto
            if pv<ex_pv:
                ex_pv=pv
                #calcolo il il pv corretto
                adj_pv=pv*(n*q/rank)
                #verifico se adj_pv è piu piccolo del precedente
                if adj_pv<ex_adj_pv:
                    #annoto il pv corretto nella lista e nell ex_BY
                    ex_adj_pv=adj_pv
                    BY_res.append(adj_pv)
                #se non lo è uso il precedente
                else:
                    adj_pv=ex_adj_pv
                    BY_res.append(ex_adj_pv)


        #riordino la lista dei risultati in ordine crescente
        BY_res=sorted(BY_res)

        return (BY_res)

################################################################################

    sys.stdout.write("\n")
    sys.stdout.write("----------------------------------------------------------"+"\n")
    sys.stdout.write("Reading "+args.sp1+" and "+args.sp2+" background data..."+"\n")


    #leggendo il file delle famiglie genero:
    #due dizionari per le due specie contente la famiglia (chiave) e i relativi geni (valori)
    plaza_diz_sp1={}
    plaza_diz_sp2={}
    #due liste con tutti gli gene ID di sp1 e sp2
    all_spID_sp1=[]
    all_spID_sp2=[]
    #due liste conteneti tutte gli ID di famiglie di sp1 e sp2 ANCHE RIPETUTI
    all_plazaID_sp1=[]
    all_plazaID_sp2=[]

    with open (args.plaza) as plaza_tab:
        for line in plaza_tab:
            line=line.split(";")
            fam=line[0]
            species=line[1]
            spID=line[2].strip("\n")
            spID=spID.strip("\r")
            #elimino il .1 o .2 in id di pomodoro
            if species=="sly":
                spID=spID[0:14]

            if species==args.sp1:
                if fam in plaza_diz_sp1:
                    plaza_diz_sp1[fam].append(spID)
                else:
                    plaza_diz_sp1[fam]=[spID]
                all_spID_sp1.append(spID)
                all_plazaID_sp1.append(fam)

            if species==args.sp2:
                if fam in plaza_diz_sp2:
                    plaza_diz_sp2[fam].append(spID)
                else:
                    plaza_diz_sp2[fam]=[spID]
                all_spID_sp2.append(spID)
                all_plazaID_sp2.append(fam)

    #conto separatamente quanti geni a sisngola copia hanno sp1 e sp2 e salvo i
    #nomi di tali famiglie in due liste
    single_copy_all_sp1=[]
    single_copy_all_sp2=[]

    for family in plaza_diz_sp1:
        if len(plaza_diz_sp1[family])==1:
            single_copy_all_sp1.append(family)

    for family in plaza_diz_sp2:
        if len(plaza_diz_sp2[family])==1:
            single_copy_all_sp2.append(family)

    #conto separatamente quante famiglie con piu di un gene hanno sp1 e sp2 e salvo i
    #nomi di tali famiglie in due liste
    multiple_memeber_all_sp1=[]
    multiple_memeber_all_sp2=[]

    for family in plaza_diz_sp1:
        if len(plaza_diz_sp1[family])>1:
            multiple_memeber_all_sp1.append(family)

    for family in plaza_diz_sp2:
        if len(plaza_diz_sp2[family])>1:
            multiple_memeber_all_sp2.append(family)


    #leggo il dizionario di sp1 e ne estraggo tutte le famiglie presenti anche
    #in sp2 con un solo membro che corrispondono a ortologhi diretti,
    #poi li salvo in un nuovo dizionario
    direct_orho_sp1_sp2={}
    #genero anche una lista che contiene solo i nomi delle famiglie di ortologhi diretti
    direct_orho_sp1_sp2_IDs=[]

    for family in plaza_diz_sp1:
        if family in plaza_diz_sp2:
            if len(plaza_diz_sp1[family])==1 and len(plaza_diz_sp2[family])==1:
                direct_orho_sp1_sp2[family]=[plaza_diz_sp1[family],plaza_diz_sp2[family]]

    direct_orho_sp1_sp2_IDs=list(direct_orho_sp1_sp2.keys())

    #genero una lista contenete TUTTE le famiglie in comune tra sp1 e sp2
    #sia orthologhi diretti che vere familgie

    very_ALL_common_families=common_elements(all_plazaID_sp1,all_plazaID_sp2)

    #dalla lisa very_ALL elimino gli ortologhi diretti
    #per ottenere una lista delle famiglie in comune con piu di un membro

    all_common_fam_sp1_sp2=[]

    for fam in very_ALL_common_families:
        if fam not in direct_orho_sp1_sp2_IDs:
            all_common_fam_sp1_sp2.append(fam)


    #genero altri due dizionari per avere corrispondenza gene (chiave) familgia (valore)

    gene_to_plaza_diz_sp1={}
    gene_to_plaza_diz_sp2={}


    with open (args.plaza) as plaza_tab:
        for line in plaza_tab:
            line=line.split(";")
            fam=line[0]
            species=line[1]
            spID=line[2].strip("\n")
            spID=spID.strip("\r")
            #elimino il .1 o .2 in id di pomodoro
            if species=="sly":
                spID=spID[0:14]

            if species==args.sp1:
                gene_to_plaza_diz_sp1[spID]=fam

            if species==args.sp2:
                gene_to_plaza_diz_sp2[spID]=fam

    sys.stdout.write("\n")
    sys.stdout.write(args.sp1+" background data:"+"\n")
    sys.stdout.write(" Genes: "+str(len(all_spID_sp1))+"\n")
    sys.stdout.write(" Families: "+str(len(unique(all_plazaID_sp1)))+"\n")
    sys.stdout.write(" of which..."+"\n")
    sys.stdout.write("  Direct orthologs: "+str(len(single_copy_all_sp1))+"\n")
    sys.stdout.write("  Multiple member families: "+ str(len(multiple_memeber_all_sp1))+"\n")

    sys.stdout.write("\n")
    sys.stdout.write(args.sp2+" background data:"+"\n")
    sys.stdout.write(" Genes: "+str(len(all_spID_sp2))+"\n")
    sys.stdout.write(" Families: "+str(len(unique(all_plazaID_sp2)))+"\n")
    sys.stdout.write(" of which..."+"\n")
    sys.stdout.write("  Direct orthologs: "+str(len(single_copy_all_sp2))+"\n")
    sys.stdout.write("  Multiple member families: "+ str(len(multiple_memeber_all_sp2))+"\n")

    sys.stdout.write("\n")
    sys.stdout.write("Intersection results:"+"\n")
    sys.stdout.write(" Families in common between "+ args.sp1+" and "+args.sp2+": "+ str(len(very_ALL_common_families))+"\n")
    sys.stdout.write(" of which..."+"\n")
    sys.stdout.write("  Direct orthologs: "+ str(len(direct_orho_sp1_sp2))+"\n")
    sys.stdout.write("  Multiple member families: "+ str(len(all_common_fam_sp1_sp2))+"\n")


################################################################################


    sys.stdout.write("\n")
    sys.stdout.write("----------------------------------------------------------"+"\n")
    sys.stdout.write("Reading "+args.sp1+" and "+args.sp2+" input data..."+"\n")

    #leggo i due file di input (liste geni DE) e genero:
    #dizionario con famiglia e relativi geni
    sig_plazaID_spID_sp1={}
    sig_plazaID_spID_sp2={}
    #lista geni
    sig_spID_sp1=[]
    sig_spID_sp2=[]
    #lista relative famiglie (ID ripetuto di famiglie con piu membri)
    sig_plazaID_sp1=[]
    sig_plazaID_sp2=[]

    #lettura file sp1

    with open (args.in_sp1) as file_sig_ID_sp1:
        for geneID in file_sig_ID_sp1:
            geneID=geneID.strip("\n")
            if geneID in gene_to_plaza_diz_sp1:
                if gene_to_plaza_diz_sp1[geneID] in sig_plazaID_spID_sp1:
                    sig_plazaID_spID_sp1[gene_to_plaza_diz_sp1[geneID]].append(geneID)
                else:
                    sig_plazaID_spID_sp1[gene_to_plaza_diz_sp1[geneID]]=[geneID]

                sig_spID_sp1.append(geneID)
                sig_plazaID_sp1.append(gene_to_plaza_diz_sp1[geneID])

    #lettura file sp2

    with open (args.in_sp2) as file_sig_ID_sp2:
        for geneID in file_sig_ID_sp2:
            geneID=geneID.strip("\n")
            if geneID in gene_to_plaza_diz_sp2:
                if gene_to_plaza_diz_sp2[geneID] in sig_plazaID_spID_sp2:
                    sig_plazaID_spID_sp2[gene_to_plaza_diz_sp2[geneID]].append(geneID)
                else:
                    sig_plazaID_spID_sp2[gene_to_plaza_diz_sp2[geneID]]=[geneID]

                sig_spID_sp2.append(geneID)
                sig_plazaID_sp2.append(gene_to_plaza_diz_sp2[geneID])

    #salvo in due liste i nomi delle famiglie di ortologhi diretti di sp1 e sp2
    single_copy_my_sp1=[]
    single_copy_my_sp2=[]
    #e in altre due liste i nomi delle famiglie con piu membri
    multiple_memeber_my_sp1=[]
    multiple_memeber_my_sp2=[]
    #uso la funzione unique sulla lista di famiglie poiche molti ID sono ripetuti

    for family in unique(sig_plazaID_sp1):
        if len(plaza_diz_sp1[family])==1:
            single_copy_my_sp1.append(family)
        else:
            multiple_memeber_my_sp1.append(family)


    for family in unique(sig_plazaID_sp2):
        if len(plaza_diz_sp2[family])==1:
            single_copy_my_sp2.append(family)
        else:
            multiple_memeber_my_sp2.append(family)


    #intersezione delle famiglie in comune
    sig_very_all_common_fam=common_elements(sig_plazaID_sp1,sig_plazaID_sp2)

    #dalle famiglie in comune estraggo quelle di ortolghi diretti e quelle con
    #piu di un membro intersecando la lista delle famiglie in comune del mio set
    #e le famiglie di orthologhi diretti e quelle a piu membri del background

    my_direct_ortho=common_elements(sig_very_all_common_fam,direct_orho_sp1_sp2)
    my_ortho_fam=common_elements(sig_very_all_common_fam, all_common_fam_sp1_sp2)

    sys.stdout.write("\n")
    sys.stdout.write(sample_sp1 + "," + args.sp1+" input data :"+"\n")
    sys.stdout.write(" Genes: "+str(len(sig_spID_sp1))+"\n")
    sys.stdout.write(" Families: "+str(len(unique(sig_plazaID_sp1)))+"\n")
    sys.stdout.write(" of which..."+"\n")
    sys.stdout.write("  Direct orthologs: "+ str(len(single_copy_my_sp1))+"\n")
    sys.stdout.write("  Multiple member families: "+ str(len(multiple_memeber_my_sp1))+"\n")

    sys.stdout.write("\n")
    sys.stdout.write(sample_sp2 + "," + args.sp2+" input data:"+"\n")
    sys.stdout.write(" Genes: "+str(len(sig_spID_sp2))+"\n")
    sys.stdout.write(" Families: "+str(len(unique(sig_plazaID_sp2)))+"\n")
    sys.stdout.write(" of which..."+"\n")
    sys.stdout.write("  Direct orthologs: "+ str(len(single_copy_my_sp2))+"\n")
    sys.stdout.write("  Multiple member families: "+ str(len(multiple_memeber_my_sp2))+"\n")

    sys.stdout.write("\n")
    sys.stdout.write("Intersection results:"+"\n")
    sys.stdout.write(" Families in common between input "+ args.sp1+" and input "+args.sp2+": "+ str(len(sig_very_all_common_fam))+"\n")
    sys.stdout.write(" of which..."+"\n")
    sys.stdout.write(" Direct orthologs: "+ str(len(my_direct_ortho))+"\n")
    sys.stdout.write(" Multiple member families: "+ str(len(my_ortho_fam))+"\n")

################################################################################

    #test per indagare se le due liste di input sono arricchiti di ortologhi diretti
    #rispetto al background

    sys.stdout.write("\n")
    sys.stdout.write("----------------------------------------------------------"+"\n")
    sys.stdout.write("Direct orthologs analysis..."+"\n")
    sys.stdout.write("\n")

    #successi, ortologhi diretti in comune
    successi=len(my_direct_ortho)

    #popolazione, prodotto del numero di otrhologhi diretti di sp1 e sp2 /2
    popolazione=(len(single_copy_all_sp1)*len(single_copy_all_sp2))/2

    #popolazione, altrenativamente come popolazione totale posso usare il numero
    #di ortolghi diretti della specie che ne ha meno

    # if len(single_copy_all_sp1)<len(single_copy_all_sp2):
    #     popolazione=len(single_copy_all_sp1)
    # else:
    #     popolazione=len(single_copy_all_sp2)

    #successi_popolazione, geni a singola copia in cumune nei due genomi
    successi_popolazione=len(direct_orho_sp1_sp2)

    #tentativi, ortologhi diretti del campione con il set di ortologhi diretti piu piccolo
    if len(single_copy_my_sp1)<len(single_copy_my_sp2):
        tentativi=len(single_copy_my_sp1)
    else:
        tentativi=len(single_copy_my_sp2)

    pv_hyp_dir_ortho=hyp_dist(successi,popolazione,successi_popolazione,tentativi)

    #calcolo l'arricchimento degli ortologhi nei due set di input rispetto al bg

    enrichment_dir_ortho=round((successi/tentativi)/(successi_popolazione/popolazione),4)

    if pv_hyp_dir_ortho<args.th_sc:
        sys.stdout.write("The intersection of the updated list is ENRICHED in direct orthologs!"+"\n")
        sys.stdout.write(" Fold change: "+str(enrichment_dir_ortho)+"\n")
        sys.stdout.write(" P.value : "+str(pv_hyp_dir_ortho)+"   (th="+str(args.th_sc)+")"+"\n")
        sys.stdout.write("\n")
        sys.stdout.write(" Direct ortologs gene IDs can be found in the result folder."+"\n")
        sys.stdout.write("\n")

    else:
        sys.stdout.write("The intersection of the updated list is NOT ENRICHED in direct orthologs!"+"\n")
        sys.stdout.write(" Fold change: "+str(enrichment_dir_ortho)+"\n")
        sys.stdout.write(" P.value : "+str(pv_hyp_dir_ortho)+"   (th="+str(args.th_sc)+")"+"\n")
        sys.stdout.write("\n")
        sys.stdout.write(" Direct ortologs gene IDs can be found in the result folder."+"\n")

################################################################################


    sys.stdout.write("----------------------------------------------------------"+"\n")
    sys.stdout.write("Computing families size distribution..."+"\n")
    sys.stdout.write("\n")

    #calcolo la distribuzione della grandezza delle famiglie, per sp1 e sp2,
    #sia per bg che input

    #come prima cosa creo dizionario con numero di membri (valore) per famiglia (chiave)
    #nel bg

    all_family_size_sp1=compute_count_list(all_plazaID_sp1)
    all_family_size_sp2=compute_count_list(all_plazaID_sp2)

    #e numero di DEGs per famiglia nel mio set

    DEGs_in_family_sp1=compute_count_list(sig_plazaID_sp1)
    DEGs_in_family_sp2=compute_count_list(sig_plazaID_sp2)

    #annoto i valori (numero mebri di ogni famiglia) dei dizionari creati in una
    #lista per poi calcolarne la frequenza

    size_list_sp1=[]
    size_list_sp2=[]

    for family in all_family_size_sp1:
        size_list_sp1.append(all_family_size_sp1[family])

    for family in all_family_size_sp2:
        size_list_sp2.append(all_family_size_sp2[family])

    #calcolo la frequenza delle grandezze

    size_freq_fam_sp1=compute_count_list(size_list_sp1)
    size_freq_fam_sp2=compute_count_list(size_list_sp2)

    sys.stdout.write(" Background families size distribution...OK"+"\n")


    #leggendo le famiglie in comune tra i due input set ed usando i dizionari
    #famiglia:size e famiglia:DEGs creo un dizionario in cui annoto come
    #chiave la grandezza della famiglia e come valore sommo il numero di geni DEGs
    #del set che hanno famiglia di quella grandezza

    DEGs_per_size_sp1={}
    DEGs_per_size_sp2={}

    #ciclo su tutte le famiglie in comune
    for family in sig_very_all_common_fam:
        #grandezza della famiglia in esame
        # print (family)
        size=all_family_size_sp1[family]
        # print (size)
        #se ho gia annotato la grandezza aggiungo il numero di DEGs
        if size in DEGs_per_size_sp1:
            DEGs_per_size_sp1[size]=DEGs_per_size_sp1[size]+DEGs_in_family_sp1[family]
        #se no creo una nuova chiave (grandezza) e annoto il numero di DEGs
        else:
            DEGs_per_size_sp1[size]=DEGs_in_family_sp1[family]
        # print (DEGs_per_size_sp1)

        size=all_family_size_sp2[family]

        if size in DEGs_per_size_sp2:
            DEGs_per_size_sp2[size]=DEGs_per_size_sp2[size]+DEGs_in_family_sp2[family]
        else:
            DEGs_per_size_sp2[size]=DEGs_in_family_sp2[family]
        # print (DEGs_per_size_sp2)
        # print ()
        # print ()

    sys.stdout.write(" Input families size distribution........OK"+"\n")
    sys.stdout.write("\n")

################################################################################

    sys.stdout.write("----------------------------------------------------------"+"\n")
    sys.stdout.write("Computing NPMI on families..."+"\n")
    sys.stdout.write("\n")

    #genero dataset con geneID random della grandezza del set di partenza
    #converto in famiglie, faccio l'intersezione e calcolo l'NPMI
    #annoto tutto in due dizionario che hanno come chiavi le famiglie in comune

    random_dataset_result_sp1={}
    random_dataset_result_sp2={}

    for fam in sig_very_all_common_fam:
        random_dataset_result_sp1[fam]=[]
        random_dataset_result_sp2[fam]=[]

    for i in range(0,args.random):

        #genero liste random di fam ID con la stessa lunghezza delle liste di input
        random_ID_sp1=random.sample(all_plazaID_sp1,len(sig_spID_sp1))

        random_ID_sp2=random.sample(all_plazaID_sp2,len(sig_spID_sp2))

        #intersezione delle due liste rando
        intersection_random=common_elements(random_ID_sp1,random_ID_sp2)

        #cicli per eliminare dalle liste random gli ID non presenti nell'altra lista
        #e generare un dizionari con i conti degli ID rimasti

        filt_random_ID_sp1=[]
        filt_random_ID_sp2=[]

        for element in random_ID_sp1:
            if element in intersection_random:
                filt_random_ID_sp1.append(element)

        count_random_sp1=compute_count_list(filt_random_ID_sp1)

        for element in random_ID_sp2:
            if element in intersection_random:
                filt_random_ID_sp2.append(element)

        count_random_sp2=compute_count_list(filt_random_ID_sp2)

        # for elementi in count_random_sp1:
        #     print (elementi, count_random_sp1[elementi])

        #per ogni famiglia calcolo il numero di geni DEGs in famiglie della
        #stessa grandezza

        random_DEGs_per_size_sp1={}
        random_DEGs_per_size_sp2={}

        #ciclo su tutte le famiglie in comune
        for family in intersection_random:
            #grandezza della famiglia in esame
            size=all_family_size_sp1[family]
            #se ho gia annotato la grandezza aggiungo il numero di DEGs
            if size in random_DEGs_per_size_sp1:
                random_DEGs_per_size_sp1[size]=random_DEGs_per_size_sp1[size]+count_random_sp1[family]
            #se no creo una nuova chiave (grandezza) e annoto il numero di DEGs
            else:
                random_DEGs_per_size_sp1[size]=count_random_sp1[family]

            size=all_family_size_sp2[family]

            if size in random_DEGs_per_size_sp2:
                random_DEGs_per_size_sp2[size]=random_DEGs_per_size_sp2[size]+count_random_sp2[family]
            else:
                random_DEGs_per_size_sp2[size]=count_random_sp2[family]


        #calcolo la NPMI per ogni famiglia e annoto nel random_dataset_result,
        #se la famiglia non è presente nel dizionario annoto

        #sp1
        for family in random_dataset_result_sp1:
            if family in count_random_sp1:

                DEGs_in_fam=float(count_random_sp1[family])
                DEGs_in_equal_size_fam=float(random_DEGs_per_size_sp1[all_family_size_sp1[family]])
                fam_size=float(all_family_size_sp1[family])
                all_gene_in_this_family_size=float(size_freq_fam_sp1[fam_size]*fam_size)

                p_my=DEGs_in_fam/DEGs_in_equal_size_fam
                p_all=(fam_size*DEGs_in_equal_size_fam)/all_gene_in_this_family_size

                if p_my==p_all or p_all==1:
                    npmi=0
                else:
                    npmi=compute_npmi(p_my,p_all)
                    if npmi < -1:
                        npmi=-1
                    if npmi>1:
                        npmi=1

                random_dataset_result_sp1[family].append(npmi)

            else:
                random_dataset_result_sp1[family].append(0)

        #sp2
        for family in random_dataset_result_sp2:
            if family in count_random_sp2:

                DEGs_in_fam=float(count_random_sp2[family])
                #print (DEGs_in_fam,"DEG in fam")
                DEGs_in_equal_size_fam=float(random_DEGs_per_size_sp2[all_family_size_sp2[family]])
                #print (DEGs_in_equal_size_fam,"DEG in equal size fam")
                fam_size=float(all_family_size_sp2[family])
                #print(fam_size,"fam size")
                all_gene_in_this_family_size=float(size_freq_fam_sp2[fam_size]*fam_size)
                #print (all_gene_in_this_family_size,"all gene in this fam size")
                #print ()
                p_my=DEGs_in_fam/DEGs_in_equal_size_fam
                #print (p_my,"p_my")
                p_all=(fam_size*DEGs_in_equal_size_fam)/all_gene_in_this_family_size
                #print (p_all,"P_all")
                if p_my==p_all or p_all==1:
                    npmi=0
                else:
                    npmi=compute_npmi(p_my,p_all)
                    if npmi < -1:
                        npmi=-1
                    if npmi>1:
                        npmi=1
                #print (npmi,"NPMI")
                random_dataset_result_sp2[family].append(npmi)
                #print ()
                #print ()

            else:
                random_dataset_result_sp2[family].append(0)
                #print ("NOT IN DIZ")

        update_progress(str(args.random)+" random datasets generation", i/args.random)
    update_progress(str(args.random)+" random datasets generation", 1)


    # for elementi in random_dataset_result_sp2:
    #     print (elementi, random_dataset_result_sp2[elementi])
################################################################################

    #creo due dizionari per annotare i valori e i risultati di ogni familgia
    #separatamente per sp1 e sp2

    result_diz_sp1={}
    result_diz_sp2={}

    family_count_sp1=compute_count_list(sig_plazaID_sp1)
    family_count_sp2=compute_count_list(sig_plazaID_sp2)

    #creo le chiavi (famiglie in comune) e annoto i valori:
    #DEGs nella familgia
    #DEGs in famiglie della stessa grandezza nel set
    #DEGS in famiglie della stessa grandezza nel genoma
    #p_my
    #p_all
    #npmi
    #p_value
    #FDR_bonf
    #FDR_BY (step successivo al sort)


    for family in sig_very_all_common_fam:

        #sp1####################################################################

        result_diz_sp1[family]=[]

        DEGs_in_fam=float(family_count_sp1[family])
        DEGs_in_equal_size_fam=float(DEGs_per_size_sp1[all_family_size_sp1[family]])
        fam_size=float(all_family_size_sp1[family])
        all_gene_in_this_family_size=float(size_freq_fam_sp1[fam_size]*fam_size)

        p_my=DEGs_in_fam/DEGs_in_equal_size_fam
        p_all=(fam_size*DEGs_in_equal_size_fam)/all_gene_in_this_family_size

        if p_my==p_all or p_all==1:
            npmi=0
        else:
            npmi=compute_npmi(p_my,p_all)
            if npmi < -1:
                npmi=-1
            if npmi>1:
                npmi=1

        higher=0

        for value in random_dataset_result_sp1[family]:
            if float(value)>=npmi:
                higher=higher+1

        p_value=float(higher)/float(args.random)

        FDR_bonf=p_value*len(sig_very_all_common_fam)
        if FDR_bonf>1:
            FDR_bonf=1

        #DEGs in fam
        result_diz_sp1[family].append(str(int(DEGs_in_fam))+"/"+str(int(fam_size)))
        #DEGs in equal size fam in set
        result_diz_sp1[family].append(int(DEGs_in_equal_size_fam))
        #DEGs in equal size fam in genome
        result_diz_sp1[family].append(int(all_gene_in_this_family_size))
        #p_my
        result_diz_sp1[family].append(round(p_my,5))
        #p_all
        result_diz_sp1[family].append(round(p_all,5))
        #NPMI
        result_diz_sp1[family].append(round(npmi,5))
        #p_value
        result_diz_sp1[family].append(round(p_value,5))
        #FDR_bonf
        result_diz_sp1[family].append(round(FDR_bonf,5))


        #sp2####################################################################

        result_diz_sp2[family]=[]

        DEGs_in_fam=float(family_count_sp2[family])
        DEGs_in_equal_size_fam=float(DEGs_per_size_sp2[all_family_size_sp2[family]])
        fam_size=float(all_family_size_sp2[family])
        all_gene_in_this_family_size=float(size_freq_fam_sp2[fam_size]*fam_size)

        p_my=DEGs_in_fam/DEGs_in_equal_size_fam
        p_all=(fam_size*DEGs_in_equal_size_fam)/all_gene_in_this_family_size

        if p_my==p_all or p_all==1:
            npmi=0
        else:
            npmi=compute_npmi(p_my,p_all)
            if npmi < -1:
                npmi=-1
            if npmi>1:
                npmi=1

        higher=0

        for value in random_dataset_result_sp2[family]:
            if float(value)>=npmi:
                higher=higher+1

        p_value=float(higher)/float(args.random)

        FDR_bonf=p_value*len(sig_very_all_common_fam)
        if FDR_bonf>1:
            FDR_bonf=1

        result_diz_sp2[family].append(str(int(DEGs_in_fam))+"/"+str(int(fam_size)))
        result_diz_sp2[family].append(int(DEGs_in_equal_size_fam))
        result_diz_sp2[family].append(int(all_gene_in_this_family_size))
        result_diz_sp2[family].append(round(p_my,5))
        result_diz_sp2[family].append(round(p_all,5))
        result_diz_sp2[family].append(round(npmi,5))
        result_diz_sp2[family].append(round(p_value,5))
        result_diz_sp2[family].append(round(FDR_bonf,5))

################################################################################

    #ordino i result_diz basandomi sul p_value (settimo elemento della lista)
    sorted_result_diz_sp1=sorted(result_diz_sp1.items(), key=lambda e: e[1][6])
    sorted_result_diz_sp2=sorted(result_diz_sp2.items(), key=lambda e: e[1][6])


    #salvo in una lista i p_value ordinati
    ord_p_value_sp1=[]
    for element in sorted_result_diz_sp1:
        ord_p_value_sp1.append(element[1][6])


    ord_p_value_sp2=[]
    for element in sorted_result_diz_sp2:
        ord_p_value_sp2.append(element[1][6])

    #calcolo i p_value_adj con BY (def) o BH method con mie funzioni
    if args.FDR=="BY":
        pv_corr_sp1= BY_FDR(ord_p_value_sp1)
        pv_corr_sp2= BY_FDR(ord_p_value_sp2)



    if args.FDR=="BH":
        pv_corr_sp1= BH_FDR(ord_p_value_sp1)
        pv_corr_sp2= BH_FDR(ord_p_value_sp2)

    #ciclo per aggiungere il pv_corr alla lista di valori di sorted_result_diz_sp1
    #per comodita poi riscrivo il result diz
    index=range(0,len(pv_corr_sp1))
    for idx in index:
        sorted_result_diz_sp1[idx][1].append(round(pv_corr_sp1[idx],5))
        sorted_result_diz_sp2[idx][1].append(round(pv_corr_sp2[idx],5))

    sorted_result_diz_sp1=dict(sorted_result_diz_sp1)
    sorted_result_diz_sp2=dict(sorted_result_diz_sp2)

    sys.stdout.write("\n")
    sys.stdout.write(" NPMI analysis results can be found in the result folder."+"\n")

################################################################################

    sys.stdout.write("\n")
    sys.stdout.write("----------------------------------------------------------"+"\n")
    sys.stdout.write("Calling significant families and genes..."+"\n")
    sys.stdout.write("\n")

    #leggo i sorted result diz per selezionare le famiglie significative ,
    #basamndomi su pv_corretti < di args.th
    #le famiglie significative le salvo in una lista per poi recuperare i geni
    #e trovare le famiglie significative in comune tra le due specie

    sig_family_sp1=[]
    sig_family_sp2=[]
    sig_genes_sp1=[]
    sig_genes_sp2=[]

    #inoltre, tengo conto dei valori di NPMI di tutte le famiglie di sp1 e sp2
    #e di tutte, per poi calcolarne la media

    sum_NPMI_sp1=0
    sum_NPMI_sp2=0
    sum_NPMI_all=0

    sum_NPMI_sp1_sig=0
    sum_NPMI_sp2_sig=0
    sum_NPMI_all_sig=0

    for family in sorted_result_diz_sp1:
        sum_NPMI_sp1=sum_NPMI_sp1+float(sorted_result_diz_sp1[family][5])
        sum_NPMI_all=sum_NPMI_all+float(sorted_result_diz_sp1[family][5])

        if sorted_result_diz_sp1[family][8]<=args.th:
            sum_NPMI_sp1_sig=sum_NPMI_sp1_sig+float(sorted_result_diz_sp1[family][5])
            sum_NPMI_all_sig=sum_NPMI_all_sig+float(sorted_result_diz_sp1[family][5])

            sig_family_sp1.append(family)
            for gene in sig_plazaID_spID_sp1[family]:
                sig_genes_sp1.append(gene)

    for family in sorted_result_diz_sp2:
        sum_NPMI_sp2=sum_NPMI_sp2+float(sorted_result_diz_sp2[family][5])
        sum_NPMI_all=sum_NPMI_all+float(sorted_result_diz_sp2[family][5])

        if sorted_result_diz_sp2[family][8]<=args.th:
            sum_NPMI_sp2_sig=sum_NPMI_sp2_sig+float(sorted_result_diz_sp2[family][5])
            sum_NPMI_all_sig=sum_NPMI_all_sig+float(sorted_result_diz_sp2[family][5])

            sig_family_sp2.append(family)
            for gene in sig_plazaID_spID_sp2[family]:
                sig_genes_sp2.append(gene)

    common_sig_family_sp1_sp2=common_elements(sig_family_sp1,sig_family_sp2)

    mean_NPMI_sp1=round(sum_NPMI_sp1/len(sorted_result_diz_sp1),4)
    mean_NPMI_sp2=round(sum_NPMI_sp2/len(sorted_result_diz_sp2),4)
    mean_NPMI_all=round(sum_NPMI_all/(len(sorted_result_diz_sp1)*2),4)

    mean_NPMI_sp1_sig=round(sum_NPMI_sp1_sig/len(sig_family_sp1),4)
    mean_NPMI_sp2_sig=round(sum_NPMI_sp2_sig/len(sig_family_sp2),4)
    mean_NPMI_all_sig=round(sum_NPMI_all_sig/(len(sig_family_sp1)+len(sig_family_sp2)),4)


    #creo un dizionariom con chiave la famiglie e due liste di vaslori per
    #relativi geni di sp1 e sp2

    diz_common_sig_family_sp1_sp2={}
    number_of_genes_in_common=0

    for family in common_sig_family_sp1_sp2:
        diz_common_sig_family_sp1_sp2[family]=[]
        diz_common_sig_family_sp1_sp2[family].append(sig_plazaID_spID_sp1[family])
        number_of_genes_in_common=number_of_genes_in_common+len(sig_plazaID_spID_sp1[family])
        diz_common_sig_family_sp1_sp2[family].append(sig_plazaID_spID_sp2[family])
        number_of_genes_in_common=number_of_genes_in_common+len(sig_plazaID_spID_sp2[family])

    sys.stdout.write(" Significant families in "+sample_sp1+": "+str(len(sig_family_sp1))+" ("+str(len(sig_genes_sp1))+" genes)"+"\n")
    sys.stdout.write(" Significant families in "+sample_sp2+": "+str(len(sig_family_sp2))+" ("+str(len(sig_genes_sp2))+" genes)"+"\n")
    sys.stdout.write(" Significant families in common: "+str(len(common_sig_family_sp1_sp2))+" ("+str(number_of_genes_in_common)+" genes)"+"\n")
    sys.stdout.write("\n")
    sys.stdout.write(" Significant families and genes IDs can be found in the result folder."+"\n")
    sys.stdout.write("\n")

################################################################################

    #scrivo gli output

    sys.stdout.write("----------------------------------------------------------"+"\n")
    sys.stdout.write("Writing outputs..."+"\n")
    sys.stdout.write("\n")

    #ortolghi diretti sia che siano significativi che non
    if pv_hyp_dir_ortho<args.th_sc:
        with open ("./"+args.sample+"_results/"+args.sample+"_significant_direct_orthologs.txt", "w") as dir_ort_out:
            dir_ort_out.write("The sample is ENRICHED in direct orthologs!"+"\n")
            dir_ort_out.write("Fold change= "+str(enrichment_dir_ortho)+"   p_value= "+str(pv_hyp_dir_ortho)+"\n")
            dir_ort_out.write("\n")
            dir_ort_out.write("Fam_ID"+"\t"+"sp1_gene"+"\t"+"sp2_gene"+"\n")
            for fam in my_direct_ortho:
                dir_ort_out.write(fam+"\t"+sig_plazaID_spID_sp1[fam][0]+"\t"+sig_plazaID_spID_sp2[fam][0]+"\n")

        sys.stdout.write(" significant_direct_orthologs..............OK"+"\n")

    else:
        with open ("./"+args.sample+"_results/"+args.sample+"_NOT_significant_direct_orthologs.txt", "w") as dir_ort_out:
            dir_ort_out.write("The sample is NOT ENRICHED in direct orthologs!"+"\n")
            dir_ort_out.write("Fold change= "+str(enrichment_dir_ortho)+"   p_value= "+str(pv_hyp_dir_ortho)+"\n")
            dir_ort_out.write("\n")
            dir_ort_out.write("Fam_ID"+"\t"+"sp1_gene"+"\t"+"sp2_gene"+"\n")
            for fam in my_direct_ortho:
                dir_ort_out.write(fam+"\t"+sig_plazaID_spID_sp1[fam][0]+"\t"+sig_plazaID_spID_sp2[fam][0]+"\n")

        sys.stdout.write(" NOT_significant_direct_orthologs..........OK"+"\n")

    #geni significativi di sp1
    with open ("./"+args.sample+"_results/"+args.sample+"_significant_genes_sp1.txt", "w") as sig_genes_sp1_out:
        for gene in sig_genes_sp1:
            sig_genes_sp1_out.write(gene+"\n")
    sys.stdout.write(" significant_genes_sp1.....................OK"+"\n")

    #geni significativi di sp2
    with open ("./"+args.sample+"_results/"+args.sample+"_significant_genes_sp2.txt", "w") as sig_genes_sp2_out:
        for gene in sig_genes_sp2:
            sig_genes_sp2_out.write(gene+"\n")
    sys.stdout.write(" significant_genes_sp2.....................OK"+"\n")

    #famiglie e geni significativi in comune
    with open ("./"+args.sample+"_results/"+args.sample+"_significant_common_families_and_genes.txt", "w") as sig_fam_genes_comm_out:
        for fam in diz_common_sig_family_sp1_sp2:
            sig_fam_genes_comm_out.write(fam+"\n")
            sig_fam_genes_comm_out.write(','.join(diz_common_sig_family_sp1_sp2[fam][0])+"\t")
            sig_fam_genes_comm_out.write(str(sorted_result_diz_sp1[fam][0])+"\n")
            sig_fam_genes_comm_out.write(','.join(diz_common_sig_family_sp1_sp2[fam][1])+"\t")
            sig_fam_genes_comm_out.write(str(sorted_result_diz_sp2[fam][0])+"\n")
            sig_fam_genes_comm_out.write("\n")
    sys.stdout.write(" significant_common_families_genes.........OK"+"\n")

    #tutti le famiglie in comune con i relativi geni
    with open ("./"+args.sample+"_results/"+args.sample+"_all_common_families_and_genes.txt", "w") as all_fam_genes_comm_out:
        for fam in sig_very_all_common_fam:
            all_fam_genes_comm_out.write(fam+"\n")
            all_fam_genes_comm_out.write(','.join(sig_plazaID_spID_sp1[fam])+"\t")
            all_fam_genes_comm_out.write(str(sorted_result_diz_sp1[fam][0])+"\n")
            all_fam_genes_comm_out.write(','.join(sig_plazaID_spID_sp2[fam])+"\t")
            all_fam_genes_comm_out.write(str(sorted_result_diz_sp2[fam][0])+"\n")
            all_fam_genes_comm_out.write("\n")
    sys.stdout.write(" all_common_families_genes.................OK"+"\n")

    #dettagli NPMI per sp1
    with open ("./"+args.sample+"_results/"+args.sample+"_NPMI_results_sp1.txt", "w") as NPMI_result_sp1_out:
        NPMI_result_sp1_out.write("Fam_ID"+"\t"+"DEGs"+"\t"+"DEGs_set"+"\t"+"DEGs_genome"+"\t"+"p_my"+"\t"+"p_all"+"\t"+"NPMI"+"\t"+"p_value"+"\t"+"FDR_Bonf"+"\t"+"FDR_"+args.FDR+"\n")
        for fam in sorted_result_diz_sp1:
            NPMI_result_sp1_out.write(fam+"\t")
            values_to_print=[]
            for value in sorted_result_diz_sp1[fam]:
                values_to_print.append(str(value))
            NPMI_result_sp1_out.write("\t".join(values_to_print))
            NPMI_result_sp1_out.write("\n")
    sys.stdout.write(" NPMI_results_sp1..........................OK"+"\n")


    #dettagli NPMI per sp2
    with open ("./"+args.sample+"_results/"+args.sample+"_NPMI_results_sp2.txt", "w") as NPMI_result_sp2_out:
        NPMI_result_sp2_out.write("Fam_ID"+"\t"+"DEGs"+"\t"+"DEGs_set"+"\t"+"DEGs_genome"+"\t"+"p_my"+"\t"+"p_all"+"\t"+"NPMI"+"\t"+"p_value"+"\t"+"FDR_Bonf"+"\t"+"FDR_"+args.FDR+"\n")
        for fam in sorted_result_diz_sp2:
            NPMI_result_sp2_out.write(fam+"\t")
            values_to_print=[]
            for value in sorted_result_diz_sp2[fam]:
                values_to_print.append(str(value))
            NPMI_result_sp2_out.write("\t".join(values_to_print))
            NPMI_result_sp2_out.write("\n")
    sys.stdout.write(" NPMI_results_sp2..........................OK"+"\n")

    #stat della run
    with open ("./"+args.sample+"_results/"+args.sample+"_stat.txt", "w") as stat_out:
        stat_out.write("----------------------------------------------------------"+"\n")
        stat_out.write("GENERAL RESULTS"+"\n")
        stat_out.write("\n")

        max_overlap=""
        if len(unique(sig_plazaID_sp1))<=len(unique(sig_plazaID_sp2)):
            max_overlap=str(len(unique(sig_plazaID_sp1)))
        else:
            max_overlap=str(len(unique(sig_plazaID_sp2)))

        stat_out.write(" Maximum of possible common families: "+max_overlap+"\n")
        stat_out.write(" Families in common: "+str(len(sig_very_all_common_fam))+"\n")
        stat_out.write("  Mean_NPMI: "+str(mean_NPMI_all)+"\n")
        stat_out.write(" Significant by NPMI test: "+str(len(common_sig_family_sp1_sp2))+"\n")
        stat_out.write("  Mean_NPMI: "+str(mean_NPMI_all_sig)+"\n")

        stat_out.write("\n")

        stat_out.write("----------------------------------------------------------"+"\n")
        stat_out.write("BACKGROUND DATA"+"\n")
        stat_out.write("\n")
        stat_out.write(args.sp1+" background data:"+"\n")
        stat_out.write(" Genes: "+str(len(all_spID_sp1))+"\n")
        stat_out.write(" Families: "+str(len(unique(all_plazaID_sp1)))+"\n")
        stat_out.write(" of which..."+"\n")
        stat_out.write("  Direct orthologs: "+str(len(single_copy_all_sp1))+"\n")
        stat_out.write("  Multiple member families: "+ str(len(multiple_memeber_all_sp1))+"\n")
        stat_out.write("\n")
        stat_out.write(args.sp2+" background data:"+"\n")
        stat_out.write(" Genes: "+str(len(all_spID_sp2))+"\n")
        stat_out.write(" Families: "+str(len(unique(all_plazaID_sp2)))+"\n")
        stat_out.write(" of which..."+"\n")
        stat_out.write("  Direct orthologs: "+str(len(single_copy_all_sp2))+"\n")
        stat_out.write("  Multiple member families: "+ str(len(multiple_memeber_all_sp2))+"\n")
        stat_out.write("\n")
        stat_out.write("Intersection results:"+"\n")
        stat_out.write(" Families in common between "+ args.sp1+" and "+args.sp2+": "+ str(len(very_ALL_common_families))+"\n")
        stat_out.write(" of which..."+"\n")
        stat_out.write("  Direct orthologs: "+ str(len(direct_orho_sp1_sp2))+"\n")
        stat_out.write("  Multiple member families: "+ str(len(all_common_fam_sp1_sp2))+"\n")
        stat_out.write("\n")

        stat_out.write("----------------------------------------------------------"+"\n")
        stat_out.write("INPUT DATA"+"\n")
        stat_out.write("\n")
        stat_out.write(sample_sp1 + "," + args.sp1+" input data :"+"\n")
        stat_out.write(" Genes: "+str(len(sig_spID_sp1))+"\n")
        stat_out.write(" Families: "+str(len(unique(sig_plazaID_sp1)))+"\n")
        stat_out.write(" of which..."+"\n")
        stat_out.write("  Direct orthologs: "+ str(len(single_copy_my_sp1))+"\n")
        stat_out.write("  Multiple member families: "+ str(len(multiple_memeber_my_sp1))+"\n")
        stat_out.write("\n")
        stat_out.write(sample_sp2 + "," + args.sp2+" input data:"+"\n")
        stat_out.write(" Genes: "+str(len(sig_spID_sp2))+"\n")
        stat_out.write(" Families: "+str(len(unique(sig_plazaID_sp2)))+"\n")
        stat_out.write(" of which..."+"\n")
        stat_out.write("  Direct orthologs: "+ str(len(single_copy_my_sp2))+"\n")
        stat_out.write("  Multiple member families: "+ str(len(multiple_memeber_my_sp2))+"\n")
        stat_out.write("\n")
        stat_out.write("Intersection results:"+"\n")
        stat_out.write(" Families in common between input "+ args.sp1+" and input "+args.sp2+": "+ str(len(sig_very_all_common_fam))+"\n")
        stat_out.write(" of which..."+"\n")
        stat_out.write(" Direct orthologs: "+ str(len(my_direct_ortho))+"\n")
        stat_out.write(" Multiple member families: "+ str(len(my_ortho_fam))+"\n")
        stat_out.write("\n")

        stat_out.write("----------------------------------------------------------"+"\n")
        stat_out.write("DIRECT ORTHOLOGS"+"\n")
        stat_out.write("\n")
        if pv_hyp_dir_ortho<args.th_sc:
            stat_out.write("The intersection of the updated list is ENRICHED in direct orthologs!"+"\n")
            stat_out.write(" Fold change: "+str(enrichment_dir_ortho)+"\n")
            stat_out.write(" P.value : "+str(pv_hyp_dir_ortho)+"   (th="+str(args.th_sc)+")"+"\n")
            stat_out.write("\n")
            stat_out.write(" Direct ortologs gene IDs can be found in the result folder."+"\n")
            stat_out.write("\n")
        else:
            stat_out.write("The intersection of the updated list is NOT ENRICHED in direct orthologs!"+"\n")
            stat_out.write(" Fold change: "+str(enrichment_dir_ortho)+"\n")
            stat_out.write(" P.value : "+str(pv_hyp_dir_ortho)+"   (th="+str(args.th_sc)+")"+"\n")
            stat_out.write("\n")
            stat_out.write(" Direct ortologs gene IDs can be found in the result folder."+"\n")
            stat_out.write("\n")

        stat_out.write("----------------------------------------------------------"+"\n")
        stat_out.write("ORTHOLOGS FAMILY"+"\n")
        stat_out.write(" Significant families in "+sample_sp1+": "+str(len(sig_family_sp1))+" ("+str(len(sig_genes_sp1))+" genes)"+"\n")
        stat_out.write("  Mean_NPMI: "+str(mean_NPMI_sp1_sig)+"\n")
        stat_out.write(" Significant families in "+sample_sp2+": "+str(len(sig_family_sp2))+" ("+str(len(sig_genes_sp2))+" genes)"+"\n")
        stat_out.write("  Mean_NPMI: "+str(mean_NPMI_sp2_sig)+"\n")
        stat_out.write(" Significant families in common: "+str(len(common_sig_family_sp1_sp2))+" ("+str(number_of_genes_in_common)+" genes)"+"\n")
        stat_out.write("  Mean_NPMI: "+str(mean_NPMI_all_sig)+"\n")
        stat_out.write("\n")
        stat_out.write(" Significant families and genes IDs can be found in the result folder."+"\n")
        stat_out.write("\n")
        stat_out.write("----------------------------------------------------------"+"\n")

        sys.stdout.write(" stat......................................OK"+"\n")
        sys.stdout.write("\n")
        sys.stdout.write("----------------------------------------------------------"+"\n")


        print(mean_NPMI_sp1)
        print(mean_NPMI_sp2)
        print(mean_NPMI_all)
        print(mean_NPMI_sp1_sig)
        print(mean_NPMI_sp2_sig)
        print(mean_NPMI_all_sig)

################################################################################


if __name__ == "__main__":
    main()
