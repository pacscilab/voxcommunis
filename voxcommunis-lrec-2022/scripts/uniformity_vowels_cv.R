require(ggrepel)
require(tidyverse)
require(ggExtra)

path <- "./data/formants_narrow/"
files <- list.files(path)

d <- data.frame()

for (i in 1:length(files)) {
  di <- read_delim(paste0(path, files[i]), delim = "\t", escape_double = FALSE, trim_ws = TRUE)
  di$lang <- gsub("_avg_formants.tsv", "", files[i])
  d <- rbind(d, di)
}

nvowels <- d %>% group_by(lang) %>% summarise(n = length(unique(vowel)))

# how many speakers are there per language
lang_counts <- d %>% group_by(lang) %>% summarise(total_token = sum(V_count_spkr), total_spkr = n())

# how many speakers produced the vowel
spkr_vowel_counts <- d %>% group_by(lang, vowel) %>% summarise(count = n())

# get means and sds
lang_means <- d %>% group_by(lang, vowel, setting) %>% summarise(meanf1 = mean(mean_f1), sdf1 = sd(mean_f1), meanf2 = mean(mean_f2), sdf2 = sd(mean_f2))

lang_means <- left_join(lang_means, lang_counts, by = "lang")
lang_means <- left_join(lang_means, spkr_vowel_counts, by = c("lang", "vowel"))

lang_means$prop <- lang_means$count / lang_means$total_spkr

f1means <- lang_means %>% filter(count >= 5) %>%
  select(lang, vowel, setting, meanf1) %>% pivot_wider(names_from = vowel, values_from = meanf1)

f2means <- lang_means %>% filter(count >= 5) %>% 
  select(lang, vowel, setting, meanf2) %>% pivot_wider(names_from = vowel, values_from = meanf2)

f1cors <- cor(f1means[,-c(1,2)], use = "pairwise.complete.obs")
f1cors <- data.frame(f1cors)
f1cors <- rownames_to_column(f1cors, "vowel1")
f1cors <- f1cors %>% pivot_longer(!vowel1, names_to = "vowel2", values_to = "cor")

f2cors <- cor(f2means[,-c(1,2)], use = "pairwise.complete.obs")
f2cors <- data.frame(f2cors)
f2cors <- rownames_to_column(f2cors, "vowel1")
f2cors <- f2cors %>% pivot_longer(!vowel1, names_to = "vowel2", values_to = "cor")

# COUNT UP THE NUMBER OF TIMES EACH VOWEL PAIR OCCURS ACROSS LANGUAGES

### for plot
count1 <- lang_means %>% 
  group_by(lang, vowel, setting) %>% 
  summarise()
count2 <- count1
cooccur <- left_join(count1, count2, by = c("lang", "setting"))
cooccur <- cooccur %>% group_by(vowel.x, vowel.y) %>% summarise(count = length(vowel.x))
colnames(cooccur) <- c("vowel1", "vowel2", "count")

f1cors <- merge(f1cors, cooccur, by = c("vowel1", "vowel2"))
f2cors <- merge(f2cors, cooccur, by = c("vowel1", "vowel2"))

### for analysis == CLEAN THIS UP
count1 <- lang_means %>% 
  group_by(lang, vowel) %>% 
  summarise()
count2 <- count1
cooccur <- left_join(count1, count2, by = c("lang"))
cooccur <- cooccur %>% 
  group_by(vowel.x, vowel.y) %>% 
  summarise(count = length(vowel.x))
colnames(cooccur) <- c("vowel1", "vowel2", "count")

f1cors <- merge(f1cors, cooccur, by = c("vowel1", "vowel2"))
f2cors <- merge(f2cors, cooccur, by = c("vowel1", "vowel2"))

#####

f1cors <- f1cors %>% na.omit() %>% 
  filter(vowel1 != vowel2) %>% 
  filter(count >= 10) %>% 
  arrange(cor) %>% 
  filter(row_number() %% 2 == 0)

f2cors <- f2cors %>% na.omit() %>% 
  filter(vowel1 != vowel2) %>% 
  filter(count >= 10) %>% 
  arrange(cor) %>% 
  filter(row_number() %% 2 == 0)

# GET P-VALUES FOR EACH CORRELATION
for (i in 1:nrow(f1cors)) {
  vowel1 <- f1cors$vowel1[i]
  vowel2 <- f1cors$vowel2[i]
  input1 <- f1means[,which(colnames(f1means) == vowel1)]
  input2 <- f1means[,which(colnames(f1means) == vowel2)]
  input1 <- as.numeric(unlist(input1))
  input2 <- as.numeric(unlist(input2))
  getcor <- cor.test(~input1 + input2)
  pval <- getcor$p.value
  f1cors$pval[i] <- pval
}

for (i in 1:nrow(f2cors)) {
  vowel1 <- f2cors$vowel1[i]
  vowel2 <- f2cors$vowel2[i]
  input1 <- f2means[,which(colnames(f2means) == vowel1)]
  input2 <- f2means[,which(colnames(f2means) == vowel2)]
  input1 <- as.numeric(unlist(input1))
  input2 <- as.numeric(unlist(input2))
  getcor <- cor.test(~input1 + input2)
  pval <- getcor$p.value
  f2cors$pval[i] <- pval
}

af1 <- subset(f1cors, pval < 0.001)
af2 <- subset(f2cors, pval < 0.001)

iuplot <- ggplot(f1means, aes(x = i, y = u, label = lang)) + 
  geom_point(aes(color = setting, shape = setting), size = 3) + 
  geom_smooth(method = lm, size = 0.75, se = T, color = "black") +
  geom_text_repel(box.padding = 0.75, arrow = arrow(length = unit(0.005, "npc"))) + 
  theme_few(20) + 
  xlab("mean /i/ F1 (Hz)") +
  ylab("mean /u/ F1 (Hz)") +
  xlim(300, 550) + ylim(300, 550) + 
  annotate("text", label = "r = 0.83, p < 0.001", x = 500, y = 300, size = 9, fontface = "italic")  +
  theme(text = element_text(size=25), plot.background = element_rect(fill = "white", color="white"), legend.position=c(0.9,0.21))

iuplot <- ggMarginal(iuplot, type = "histogram", xparams = list(color = "gray48", fill = "white"), yparams = list(color = "white", fill = "gray48"))

ggsave("~/Desktop/iu_f1.pdf", plot = iuplot, height = 7, width = 10, units = "in", dpi = 300)

ieplot <- ggplot(f1means, aes(x = i, y = e, label = lang)) + 
  geom_point(aes(color = setting, shape = setting), size = 3) + 
  geom_smooth(method = lm, size = 0.75, se = T, color = "black") +
  geom_text_repel(box.padding = 0.75, arrow = arrow(length = unit(0.005, "npc"))) + 
  theme_few(20) + 
  xlab("mean /i/ F1 (Hz)") +
  ylab("mean /e/ F1 (Hz)") +
  xlim(300, 550) + ylim(300, 550) + 
  annotate("text", label = "r = 0.18, p > 0.05", x = 500, y = 300, size = 9, fontface = "italic")  +
  theme(text = element_text(size=25), plot.background = element_rect(fill = "white", color="white"), legend.position=c(0.9,0.21))

ieplot <- ggMarginal(ieplot, type = "histogram", xparams = list(color = "gray48", fill = "white"), yparams = list(color = "white", fill = "gray48"))

ggsave("~/Desktop/ie_f1.pdf", plot = ieplot, height = 7, width = 10, units = "in", dpi = 300)



uoplot <- ggplot(f1means, aes(x = u, y = o, label = lang)) + 
  geom_point(aes(color = setting, shape = setting), size = 3) + 
  geom_smooth(method = lm, size = 0.75, se = T, color = "black") +
  geom_text_repel(box.padding = 0.75, arrow = arrow(length = unit(0.005, "npc"))) + 
  theme_few(20) + 
  xlab("mean /u/ F1 (Hz)") +
  ylab("mean /o/ F1 (Hz)") +
  xlim(300, 550) + ylim(300, 550) + 
  annotate("text", label = "r = 0.46, p < 0.001", x = 500, y = 300, size = 9, fontface = "italic")  +
  theme(text = element_text(size=25), plot.background = element_rect(fill = "white", color="white"), legend.position=c(0.9,0.21))

uoplot <- ggMarginal(uoplot, type = "histogram", xparams = list(color = "gray48", fill = "white"), yparams = list(color = "white", fill = "gray48"))

ggsave("~/Desktop/uo_f1.pdf", plot = uoplot, height = 7, width = 10, units = "in", dpi = 300)

p <- ggplot(f1means, aes(x = e, y = o, label = lang)) + 
  geom_point(aes(color = setting, shape = setting), size = 3) + 
  geom_smooth(method = lm, size = 0.75, se = T, color = "black") +
  geom_text_repel(box.padding = 0.75, arrow = arrow(length = unit(0.005, "npc"))) + 
  theme_few(20) + 
  xlab("mean /e/ F1 (Hz)") +
  ylab("mean /o/ F1 (Hz)") +
  xlim(375, 550) + ylim(375, 550) + 
  #geom_abline(intercept = 0, slope = 1, style = "dashed") + 
  annotate("text", label = "r = 0.74, p < 0.001", x = 515, y = 375, size = 9, fontface = "italic") +
  theme(text = element_text(size=25), plot.background = element_rect(fill = "white", color="white"), legend.position=c(0.9,0.21))

p <- ggMarginal(p, type = "histogram", xparams = list(color = "gray48", fill = "white"), yparams = list(color = "white", fill = "gray48"))

ggsave("~/Desktop/eo_f1.pdf", plot = p, height = 7, width = 10, units = "in", dpi = 300)
