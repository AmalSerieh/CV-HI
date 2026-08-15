import {
  Document,
  Packer,
  Paragraph,
  TextRun,
  HeadingLevel,
  BorderStyle,
  AlignmentType,
  Table,
  TableRow,
  TableCell,
  WidthType
} from 'docx';

export async function generateDocxReport(report, template = 'single_column') {
  if (template === 'two_column' || template === 'modern' || template === 'amani') {
    return await generateTwoColumnReport(report);
  }
  return await generateSingleColumnReport(report);
}

// Helper to resolve dynamic section titles
function getSectionHeading(secKey, rawSections = {}) {
  if (rawSections[secKey] && rawSections[secKey].heading) {
    return rawSections[secKey].heading;
  }
  return secKey.replace(/_/g, ' ').toUpperCase();
}

// TEMPLATE 1: Mohammed Al-Dossari Style (Classic Single Column ATS)
async function generateSingleColumnReport(report) {
  const contact = report?.entities?.contact || {};
  const summaryOriginal = report?.entities?.summary || '';
  const summaryImproved = report?.rewrites?.summary?.improved || '';
  const skills = report?.entities?.skills || [];
  const skillGroups = report?.rewrites?.skills_section?.improved_groups || [];
  const experiences = report?.entities?.experience || [];
  const bulletRewrites = report?.rewrites?.experience_bullets || [];
  const projects = report?.entities?.projects || [];
  const education = report?.entities?.education || [];
  const certs = report?.entities?.certifications || [];
  const rawSections = report?.extraction?.sections || {};

  // Build section order dynamically from extraction or rawSections keys, filtering out empty sections
  const extractedOrder = report?.extraction?.section_order || [];
  const candidateKeys = Array.from(new Set([
    ...extractedOrder,
    ...Object.keys(rawSections),
    ...Object.keys(report?.entities || {})
  ])).filter(k => k !== 'contact' && k !== 'contact_header');

  const hasSectionContent = (secKey) => {
    if (secKey === 'summary') {
      return Boolean(summaryImproved?.trim() || summaryOriginal?.trim() || rawSections.summary?.content?.trim());
    }
    if (secKey === 'skills') {
      return Boolean((skillGroups && skillGroups.length > 0) || (skills && skills.length > 0) || rawSections.skills?.content?.trim());
    }
    if (secKey === 'experience') {
      return Boolean((experiences && experiences.length > 0) || rawSections.experience?.content?.trim());
    }
    if (secKey === 'education') {
      return Boolean((education && education.length > 0) || rawSections.education?.content?.trim());
    }
    if (secKey === 'projects') {
      return Boolean((projects && projects.length > 0) || rawSections.projects?.content?.trim());
    }
    const rawContent = rawSections[secKey]?.content?.trim() || (typeof report?.entities?.[secKey] === 'string' ? report.entities[secKey].trim() : null);
    const entityData = report?.entities?.[secKey];
    if (Array.isArray(entityData) && entityData.length > 0) return true;
    return Boolean(rawContent);
  };

  const allSectionKeys = candidateKeys.filter(hasSectionContent);

  const children = [];

  // 1. CANDIDATE HEADER
  const candidateName = contact.name || report?.document?.name?.replace(/\.[^/.]+$/, "") || "Candidate Name";
  const targetRoleObj = report?.target_role || {};
  const primaryRoleObj = targetRoleObj.primary || {};
  const jobTitle = contact.job_title || primaryRoleObj.title_en || "";

  children.push(
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 100, after: 40 },
      children: [
        new TextRun({
          text: candidateName.toUpperCase(),
          bold: true,
          size: 32, // 16pt
          color: "000000",
          font: "Arial"
        })
      ]
    })
  );

  if (jobTitle) {
    children.push(
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 60 },
        children: [
          new TextRun({
            text: jobTitle,
            size: 22, // 11pt
            color: "4A5568",
            font: "Arial"
          })
        ]
      })
    );
  }

  // Contact Info Line
  const contactDetails = [];
  if (contact.phone) contactDetails.push(contact.phone);
  if (contact.location) contactDetails.push(contact.location);
  if (contact.email) contactDetails.push(contact.email);
  if (contact.portfolio) contactDetails.push(contact.portfolio.replace(/^https?:\/\/(www\.)?/, ''));
  if (contact.linkedin) contactDetails.push(contact.linkedin.replace(/^https?:\/\/(www\.)?/, ''));
  if (contact.github) contactDetails.push(contact.github.replace(/^https?:\/\/(www\.)?/, ''));

  if (contactDetails.length > 0) {
    children.push(
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 200 },
        children: [
          new TextRun({
            text: contactDetails.join("  |  "),
            size: 18, // 9pt
            color: "2D3748",
            font: "Arial"
          })
        ]
      })
    );
  }

  // Section Heading Generator
  const createSectionHeader = (title) => {
    return new Paragraph({
      heading: HeadingLevel.HEADING_2,
      spacing: { before: 240, after: 120 },
      border: {
        bottom: { style: BorderStyle.SINGLE, size: 8, color: "000000" }
      },
      children: [
        new TextRun({
          text: title.toUpperCase(),
          bold: true,
          size: 22, // 11pt
          color: "000000",
          font: "Arial"
        })
      ]
    });
  };

  // Entry Header (Title + Company / Date)
  const createEntryHeader = (titleText, subText, dateText) => {
    return new Table({
      width: { size: 100, type: WidthType.PERCENTAGE },
      borders: {
        top: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
        bottom: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
        left: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
        right: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
        insideHorizontal: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
        insideVertical: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
      },
      rows: [
        new TableRow({
          children: [
            new TableCell({
              width: { size: 70, type: WidthType.PERCENTAGE },
              children: [
                new Paragraph({
                  spacing: { before: 80, after: 20 },
                  children: [
                    new TextRun({ text: titleText, bold: true, size: 21, color: "000000", font: "Arial" })
                  ]
                }),
                ...(subText ? [
                  new Paragraph({
                    spacing: { after: 40 },
                    children: [
                      new TextRun({ text: subText, italic: true, size: 19, color: "333333", font: "Arial" })
                    ]
                  })
                ] : [])
              ]
            }),
            new TableCell({
              width: { size: 30, type: WidthType.PERCENTAGE },
              children: [
                new Paragraph({
                  alignment: AlignmentType.RIGHT,
                  spacing: { before: 80, after: 20 },
                  children: [
                    new TextRun({ text: dateText || "", size: 19, color: "333333", font: "Arial" })
                  ]
                })
              ]
            })
          ]
        })
      ]
    });
  };

  // Render sections dynamically according to allSectionKeys
  for (const secKey of allSectionKeys) {
    const heading = getSectionHeading(secKey, rawSections);

    if (secKey === 'summary') {
      const text = summaryImproved || summaryOriginal || rawSections.summary?.content;
      if (text && text.trim().length > 0) {
        children.push(createSectionHeader(heading));
        children.push(
          new Paragraph({
            spacing: { before: 60, after: 120 },
            children: [new TextRun({ text: text.trim(), size: 20, font: "Arial" })]
          })
        );
      }
    } else if (secKey === 'skills') {
      if ((skillGroups && skillGroups.length > 0) || (skills && skills.length > 0) || rawSections.skills?.content) {
        children.push(createSectionHeader(heading));
        if (skillGroups && skillGroups.length > 0) {
          for (const grp of skillGroups) {
            const items = Array.isArray(grp.items) ? grp.items.join(", ") : String(grp.items);
            children.push(
              new Paragraph({
                bullet: { level: 0 },
                spacing: { before: 20, after: 30 },
                children: [
                  new TextRun({ text: `${grp.group}: `, bold: true, size: 19, font: "Arial" }),
                  new TextRun({ text: items, size: 19, font: "Arial" })
                ]
              })
            );
          }
        } else if (skills && skills.length > 0) {
          const skillList = Array.isArray(skills)
            ? skills.map(s => typeof s === 'string' ? s : s.value || s.name || s.skill || '').filter(Boolean)
            : [String(skills)];
          for (const item of skillList) {
            children.push(
              new Paragraph({
                bullet: { level: 0 },
                spacing: { before: 20, after: 30 },
                children: [new TextRun({ text: item, size: 19, font: "Arial" })]
              })
            );
          }
        } else if (rawSections.skills?.content) {
          const lines = rawSections.skills.content.split('\n').filter(Boolean);
          for (const l of lines) {
            children.push(
              new Paragraph({
                spacing: { after: 30 },
                children: [new TextRun({ text: l.trim(), size: 19, font: "Arial" })]
              })
            );
          }
        }
      }
    } else if (secKey === 'experience') {
      if ((experiences && experiences.length > 0) || rawSections.experience?.content) {
        children.push(createSectionHeader(heading));
        if (experiences && experiences.length > 0) {
          for (const exp of experiences) {
            const title = exp.job_title || exp.role || exp.title || exp.position || "Position";
            const company = exp.company || exp.organization || "";
            const location = exp.location || "";
            const subText = [company, location].filter(Boolean).join(", ");
            const dateText = exp.dates || exp.duration || exp.period || (exp.start_date ? `${exp.start_date} – ${exp.end_date || 'Present'}` : "");

            children.push(createEntryHeader(title, subText, dateText));

            if (exp.description) {
              children.push(
                new Paragraph({
                  spacing: { after: 40 },
                  children: [new TextRun({ text: exp.description, size: 19, font: "Arial" })]
                })
              );
            }

            const responsibilities = Array.isArray(exp.responsibilities) ? exp.responsibilities : [];
            const bullets = Array.isArray(exp.bullets) ? exp.bullets : (exp.bullet_points || []);
            const allBullets = responsibilities.length > 0 ? responsibilities : bullets;

            for (const bullet of allBullets) {
              const bulletStr = typeof bullet === 'string' ? bullet : bullet.text || '';
              if (!bulletStr) continue;

              const matchedRewrite = bulletRewrites.find(b => b.original && b.original.trim() === bulletStr.trim() && b.improved);
              const finalBulletText = matchedRewrite ? matchedRewrite.improved : bulletStr.replace(/^•\s*/, '');

              children.push(
                new Paragraph({
                  bullet: { level: 0 },
                  spacing: { before: 20, after: 30 },
                  children: [new TextRun({ text: finalBulletText, size: 19, font: "Arial" })]
                })
              );
            }
          }
        } else if (rawSections.experience?.content) {
          const lines = rawSections.experience.content.split('\n').filter(Boolean);
          for (const l of lines) {
            children.push(
              new Paragraph({
                bullet: l.trim().startsWith('•') || l.trim().startsWith('-') ? { level: 0 } : undefined,
                spacing: { after: 30 },
                children: [new TextRun({ text: l.replace(/^[•-]\s*/, ''), size: 19, font: "Arial" })]
              })
            );
          }
        }
      }
    } else if (secKey === 'education') {
      if ((education && education.length > 0) || rawSections.education?.content) {
        children.push(createSectionHeader(heading));
        if (education && education.length > 0) {
          for (const edu of education) {
            const deg = edu.degree || edu.institution || edu.title || "Degree";
            const inst = edu.description || edu.school || (deg !== edu.institution ? edu.institution : "");
            const loc = edu.location ? `, ${edu.location}` : "";
            const subText = inst ? `${inst}${loc}` : "";
            const yr = edu.year || edu.dates || (edu.start_date ? `${edu.start_date} – ${edu.end_date || ''}` : (edu.graduation_year ? `Graduated: ${edu.graduation_year}` : ""));

            children.push(createEntryHeader(deg, subText, yr));
          }
        } else if (rawSections.education?.content) {
          const lines = rawSections.education.content.split('\n').filter(Boolean);
          for (const l of lines) {
            children.push(
              new Paragraph({
                spacing: { after: 30 },
                children: [new TextRun({ text: l.trim(), size: 19, font: "Arial" })]
              })
            );
          }
        }
      }
    } else if (secKey === 'projects') {
      const projectContent = (projects && projects.length > 0) ? null : rawSections.projects?.content;
      if ((projects && projects.length > 0) || projectContent) {
        children.push(createSectionHeader(heading));
        if (projects && projects.length > 0) {
          for (const proj of projects) {
            const name = proj.name || proj.title || "Project";
            const desc = proj.description || "";
            const tech = proj.technologies ? (Array.isArray(proj.technologies) ? proj.technologies.join(", ") : proj.technologies) : "";

            children.push(
              new Paragraph({
                spacing: { before: 60, after: 20 },
                children: [
                  new TextRun({ text: name, bold: true, size: 20, color: "000000", font: "Arial" }),
                  new TextRun({ text: tech ? `  [${tech}]` : "", italic: true, size: 18, color: "4A5568", font: "Arial" })
                ]
              })
            );
            if (desc) {
              children.push(
                new Paragraph({
                  bullet: { level: 0 },
                  spacing: { after: 30 },
                  children: [new TextRun({ text: desc, size: 19, font: "Arial" })]
                })
              );
            }
          }
        } else if (projectContent) {
          const lines = projectContent.split('\n').filter(Boolean);
          for (const l of lines) {
            children.push(
              new Paragraph({
                bullet: { level: 0 },
                spacing: { after: 30 },
                children: [new TextRun({ text: l.replace(/^[•-]\s*/, ''), size: 19, font: "Arial" })]
              })
            );
          }
        }
      }
    } else {
      // Dynamic fallback for any other custom section (e.g. certifications, publications, languages, achievements, etc.)
      const rawContent = rawSections[secKey]?.content || (typeof report?.entities?.[secKey] === 'string' ? report.entities[secKey] : null);
      const entityData = report?.entities?.[secKey];

      if (rawContent || (Array.isArray(entityData) && entityData.length > 0)) {
        children.push(createSectionHeader(heading));
        if (Array.isArray(entityData) && entityData.length > 0) {
          for (const item of entityData) {
            const itemStr = typeof item === 'string' ? item : (item.name || item.title || item.value || JSON.stringify(item));
            children.push(
              new Paragraph({
                bullet: { level: 0 },
                spacing: { after: 30 },
                children: [new TextRun({ text: itemStr, size: 19, font: "Arial" })]
              })
            );
          }
        } else if (rawContent) {
          const lines = rawContent.split('\n').filter(Boolean);
          for (const l of lines) {
            const isBullet = l.trim().startsWith('•') || l.trim().startsWith('-');
            children.push(
              new Paragraph({
                bullet: isBullet ? { level: 0 } : undefined,
                spacing: { after: 30 },
                children: [new TextRun({ text: l.replace(/^[•-]\s*/, '').trim(), size: 19, font: "Arial" })]
              })
            );
          }
        }
      }
    }
  }

  const doc = new Document({
    sections: [
      {
        properties: {},
        children
      }
    ]
  });

  return await Packer.toBuffer(doc);
}

// TEMPLATE 2: Amani al-Maliki Style (Modern Two Column / Sidebar)
async function generateTwoColumnReport(report) {
  const contact = report?.entities?.contact || {};
  const summaryOriginal = report?.entities?.summary || '';
  const summaryImproved = report?.rewrites?.summary?.improved || '';
  const skills = report?.entities?.skills || [];
  const skillGroups = report?.rewrites?.skills_section?.improved_groups || [];
  const experiences = report?.entities?.experience || [];
  const bulletRewrites = report?.rewrites?.experience_bullets || [];
  const projects = report?.entities?.projects || [];
  const education = report?.entities?.education || [];
  const certs = report?.entities?.certifications || [];
  const languages = report?.entities?.languages || [];
  const rawSections = report?.extraction?.sections || {};

  const candidateName = contact.name || report?.document?.name?.replace(/\.[^/.]+$/, "") || "Candidate Name";
  const targetRoleObj = report?.target_role || {};
  const primaryRoleObj = targetRoleObj.primary || {};
  const jobTitle = contact.job_title || primaryRoleObj.title_en || "";

  const createSubSectionHeader = (title, color = "0F2942") => {
    return new Paragraph({
      heading: HeadingLevel.HEADING_3,
      spacing: { before: 180, after: 80 },
      border: {
        bottom: { style: BorderStyle.SINGLE, size: 6, color: color }
      },
      children: [
        new TextRun({
          text: title.toUpperCase(),
          bold: true,
          size: 20, // 10pt
          color: color,
          font: "Arial"
        })
      ]
    });
  };

  // Define keys that naturally belong in the right sidebar
  const SIDEBAR_KEYS = new Set(['skills', 'languages', 'certifications', 'awards', 'interests', 'contact']);

  const extractedOrder = report?.extraction?.section_order || [];
  const candidateKeys = Array.from(new Set([
    ...extractedOrder,
    ...Object.keys(rawSections),
    ...Object.keys(report?.entities || {})
  ])).filter(k => k !== 'contact' && k !== 'contact_header');

  const hasSectionContent = (secKey) => {
    if (secKey === 'summary') {
      return Boolean(summaryImproved?.trim() || summaryOriginal?.trim() || rawSections.summary?.content?.trim());
    }
    if (secKey === 'skills') {
      return Boolean((skillGroups && skillGroups.length > 0) || (skills && skills.length > 0) || rawSections.skills?.content?.trim());
    }
    if (secKey === 'experience') {
      return Boolean((experiences && experiences.length > 0) || rawSections.experience?.content?.trim());
    }
    if (secKey === 'education') {
      return Boolean((education && education.length > 0) || rawSections.education?.content?.trim());
    }
    if (secKey === 'projects') {
      return Boolean((projects && projects.length > 0) || rawSections.projects?.content?.trim());
    }
    const rawContent = rawSections[secKey]?.content?.trim() || (typeof report?.entities?.[secKey] === 'string' ? report.entities[secKey].trim() : null);
    const entityData = report?.entities?.[secKey];
    if (Array.isArray(entityData) && entityData.length > 0) return true;
    return Boolean(rawContent);
  };

  const allSectionKeys = candidateKeys.filter(hasSectionContent);

  // LEFT MAIN COLUMN (68% Width)
  const leftChildren = [];

  leftChildren.push(
    new Paragraph({
      spacing: { before: 0, after: 40 },
      children: [
        new TextRun({
          text: candidateName,
          bold: true,
          size: 34, // 17pt
          color: "0F2942",
          font: "Arial"
        })
      ]
    })
  );

  if (jobTitle) {
    leftChildren.push(
      new Paragraph({
        spacing: { after: 120 },
        children: [
          new TextRun({
            text: jobTitle,
            size: 22, // 11pt
            color: "4A5568",
            font: "Arial"
          })
        ]
      })
    );
  }

  const summaryText = summaryImproved || summaryOriginal || rawSections.summary?.content;
  if (summaryText && summaryText.trim().length > 0) {
    leftChildren.push(
      new Paragraph({
        spacing: { before: 40, after: 160 },
        children: [
          new TextRun({ text: summaryText.trim(), size: 19, font: "Arial", color: "2D3748" })
        ]
      })
    );
  }

  // Iterate over main body sections
  for (const secKey of allSectionKeys) {
    if (SIDEBAR_KEYS.has(secKey) || secKey === 'summary') continue;
    const heading = getSectionHeading(secKey, rawSections);

    if (secKey === 'experience') {
      if ((experiences && experiences.length > 0) || rawSections.experience?.content) {
        leftChildren.push(createSubSectionHeader(heading, "0F2942"));
        if (experiences && experiences.length > 0) {
          for (const exp of experiences) {
            const title = exp.job_title || exp.role || exp.title || exp.position || "Position";
            const company = exp.company || exp.organization || "";
            const location = exp.location || "";
            const subText = [company, location].filter(Boolean).join(" – ");
            const dateText = exp.dates || exp.duration || exp.period || (exp.start_date ? `${exp.start_date} – ${exp.end_date || 'Present'}` : "");

            leftChildren.push(
              new Paragraph({
                spacing: { before: 100, after: 20 },
                children: [
                  new TextRun({ text: title, bold: true, size: 20, color: "000000", font: "Arial" }),
                  new TextRun({ text: dateText ? `  (${dateText})` : "", italic: true, size: 18, color: "718096", font: "Arial" })
                ]
              })
            );

            if (subText) {
              leftChildren.push(
                new Paragraph({
                  spacing: { after: 40 },
                  children: [new TextRun({ text: subText, italic: true, size: 19, color: "4A5568", font: "Arial" })]
                })
              );
            }

            const responsibilities = Array.isArray(exp.responsibilities) ? exp.responsibilities : [];
            const bullets = Array.isArray(exp.bullets) ? exp.bullets : (exp.bullet_points || []);
            const allBullets = responsibilities.length > 0 ? responsibilities : bullets;

            for (const bullet of allBullets) {
              const bulletStr = typeof bullet === 'string' ? bullet : bullet.text || '';
              if (!bulletStr) continue;

              const matchedRewrite = bulletRewrites.find(b => b.original && b.original.trim() === bulletStr.trim() && b.improved);
              const finalBulletText = matchedRewrite ? matchedRewrite.improved : bulletStr.replace(/^•\s*/, '');

              leftChildren.push(
                new Paragraph({
                  bullet: { level: 0 },
                  spacing: { before: 20, after: 30 },
                  children: [new TextRun({ text: finalBulletText, size: 19, font: "Arial", color: "2D3748" })]
                })
              );
            }
          }
        } else if (rawSections.experience?.content) {
          const lines = rawSections.experience.content.split('\n').filter(Boolean);
          for (const l of lines) {
            leftChildren.push(
              new Paragraph({
                bullet: l.trim().startsWith('•') || l.trim().startsWith('-') ? { level: 0 } : undefined,
                spacing: { after: 30 },
                children: [new TextRun({ text: l.replace(/^[•-]\s*/, ''), size: 19, font: "Arial" })]
              })
            );
          }
        }
      }
    } else if (secKey === 'education') {
      if ((education && education.length > 0) || rawSections.education?.content) {
        leftChildren.push(createSubSectionHeader(heading, "0F2942"));
        if (education && education.length > 0) {
          for (const edu of education) {
            const deg = edu.degree || edu.institution || edu.title || "Degree";
            const inst = edu.description || edu.school || (deg !== edu.institution ? edu.institution : "");
            const loc = edu.location ? `, ${edu.location}` : "";
            const yr = edu.year || edu.dates || (edu.start_date ? `${edu.start_date} – ${edu.end_date || ''}` : (edu.graduation_year ? `Graduated: ${edu.graduation_year}` : ""));

            leftChildren.push(
              new Paragraph({
                spacing: { before: 80, after: 20 },
                children: [
                  new TextRun({ text: deg, bold: true, size: 20, color: "000000", font: "Arial" }),
                  new TextRun({ text: yr ? `  (${yr})` : "", italic: true, size: 18, color: "718096", font: "Arial" })
                ]
              })
            );
            if (inst) {
              leftChildren.push(
                new Paragraph({
                  spacing: { after: 40 },
                  children: [new TextRun({ text: `${inst}${loc}`, italic: true, size: 19, color: "4A5568", font: "Arial" })]
                })
              );
            }
          }
        } else if (rawSections.education?.content) {
          const lines = rawSections.education.content.split('\n').filter(Boolean);
          for (const l of lines) {
            leftChildren.push(
              new Paragraph({
                spacing: { after: 30 },
                children: [new TextRun({ text: l.trim(), size: 19, font: "Arial" })]
              })
            );
          }
        }
      }
    } else if (secKey === 'projects') {
      const projectContent = (projects && projects.length > 0) ? null : rawSections.projects?.content;
      if ((projects && projects.length > 0) || projectContent) {
        leftChildren.push(createSubSectionHeader(heading, "0F2942"));
        if (projects && projects.length > 0) {
          for (const proj of projects) {
            const name = proj.name || proj.title || "Project";
            const desc = proj.description || "";
            leftChildren.push(
              new Paragraph({
                spacing: { before: 60, after: 20 },
                children: [new TextRun({ text: name, bold: true, size: 19, font: "Arial" })]
              })
            );
            if (desc) {
              leftChildren.push(
                new Paragraph({
                  bullet: { level: 0 },
                  spacing: { after: 30 },
                  children: [new TextRun({ text: desc, size: 18, font: "Arial" })]
                })
              );
            }
          }
        }
      }
    } else {
      const rawContent = rawSections[secKey]?.content || (typeof report?.entities?.[secKey] === 'string' ? report.entities[secKey] : null);
      if (rawContent) {
        leftChildren.push(createSubSectionHeader(heading, "0F2942"));
        const lines = rawContent.split('\n').filter(Boolean);
        for (const l of lines) {
          const isBullet = l.trim().startsWith('•') || l.trim().startsWith('-');
          leftChildren.push(
            new Paragraph({
              bullet: isBullet ? { level: 0 } : undefined,
              spacing: { after: 30 },
              children: [new TextRun({ text: l.replace(/^[•-]\s*/, '').trim(), size: 19, font: "Arial" })]
            })
          );
        }
      }
    }
  }

  // RIGHT SIDEBAR COLUMN (32% Width)
  const rightChildren = [];

  // Contact Info Section (Only render if contact fields exist)
  if (contact.phone || contact.email || contact.location || contact.linkedin || contact.github || contact.portfolio) {
    rightChildren.push(createSubSectionHeader("Contact", "0F2942"));
    if (contact.phone) {
      rightChildren.push(new Paragraph({ spacing: { after: 20 }, children: [
        new TextRun({ text: contact.phone, size: 18, font: "Arial", color: "1A202C" })
      ]}));
    }
    if (contact.email) {
      rightChildren.push(new Paragraph({ spacing: { after: 20 }, children: [
        new TextRun({ text: contact.email, size: 18, font: "Arial", color: "1A202C" })
      ]}));
    }
    if (contact.location) {
      rightChildren.push(new Paragraph({ spacing: { after: 20 }, children: [
        new TextRun({ text: contact.location, size: 18, font: "Arial", color: "1A202C" })
      ]}));
    }
    if (contact.linkedin || contact.github || contact.portfolio) {
      const linkStr = [contact.linkedin, contact.github, contact.portfolio].filter(Boolean).map(l => l.replace(/^https?:\/\/(www\.)?/, '')).join("\n");
      rightChildren.push(new Paragraph({ spacing: { after: 20 }, children: [
        new TextRun({ text: linkStr, size: 17, font: "Arial", color: "2B6CB0" })
      ]}));
    }
  }

  // Sidebar Sections (Skills, Languages, Certifications, etc.)
  for (const secKey of allSectionKeys) {
    if (!SIDEBAR_KEYS.has(secKey)) continue;
    const heading = getSectionHeading(secKey, rawSections);

    if (secKey === 'skills') {
      if ((skillGroups && skillGroups.length > 0) || (skills && skills.length > 0) || rawSections.skills?.content) {
        rightChildren.push(createSubSectionHeader(heading, "0F2942"));
        if (skillGroups && skillGroups.length > 0) {
          for (const grp of skillGroups) {
            const items = Array.isArray(grp.items) ? grp.items.join(", ") : String(grp.items);
            rightChildren.push(
              new Paragraph({
                spacing: { before: 30, after: 10 },
                children: [new TextRun({ text: `${grp.group}:`, bold: true, size: 18, font: "Arial", color: "2D3748" })]
              })
            );
            rightChildren.push(
              new Paragraph({
                bullet: { level: 0 },
                spacing: { after: 30 },
                children: [new TextRun({ text: items, size: 18, font: "Arial" })]
              })
            );
          }
        } else if (skills && skills.length > 0) {
          const skillList = Array.isArray(skills)
            ? skills.map(s => typeof s === 'string' ? s : s.value || s.name || s.skill || '').filter(Boolean)
            : [String(skills)];
          for (const item of skillList) {
            rightChildren.push(
              new Paragraph({
                bullet: { level: 0 },
                spacing: { before: 10, after: 20 },
                children: [new TextRun({ text: item, size: 18, font: "Arial" })]
              })
            );
          }
        }
      }
    } else if (secKey === 'languages') {
      if ((languages && languages.length > 0) || rawSections.languages?.content) {
        rightChildren.push(createSubSectionHeader(heading, "0F2942"));
        if (languages && languages.length > 0) {
          for (const lang of languages) {
            const langStr = typeof lang === 'string' ? lang : (lang.language ? `${lang.language}${lang.proficiency ? `: ${lang.proficiency}` : ''}` : '');
            if (langStr) {
              rightChildren.push(
                new Paragraph({
                  bullet: { level: 0 },
                  spacing: { after: 20 },
                  children: [new TextRun({ text: langStr, size: 18, font: "Arial" })]
                })
              );
            }
          }
        } else if (rawSections.languages?.content) {
          const lines = rawSections.languages.content.split('\n').filter(Boolean);
          for (const l of lines) {
            rightChildren.push(
              new Paragraph({
                bullet: { level: 0 },
                spacing: { after: 20 },
                children: [new TextRun({ text: l.replace(/^[•-]\s*/, ''), size: 18, font: "Arial" })]
              })
            );
          }
        }
      }
    } else if (secKey === 'certifications') {
      if ((certs && certs.length > 0) || rawSections.certifications?.content) {
        rightChildren.push(createSubSectionHeader(heading, "0F2942"));
        if (certs && certs.length > 0) {
          for (const cert of certs) {
            const cName = typeof cert === 'string' ? cert : (cert.name || cert.title || '');
            if (cName) {
              rightChildren.push(
                new Paragraph({
                  bullet: { level: 0 },
                  spacing: { after: 20 },
                  children: [new TextRun({ text: cName, size: 18, font: "Arial" })]
                })
              );
            }
          }
        } else if (rawSections.certifications?.content) {
          const lines = rawSections.certifications.content.split('\n').filter(Boolean);
          for (const l of lines) {
            rightChildren.push(
              new Paragraph({
                bullet: { level: 0 },
                spacing: { after: 20 },
                children: [new TextRun({ text: l.replace(/^[•-]\s*/, ''), size: 18, font: "Arial" })]
              })
            );
          }
        }
      }
    } else {
      const rawContent = rawSections[secKey]?.content;
      if (rawContent) {
        rightChildren.push(createSubSectionHeader(heading, "0F2942"));
        const lines = rawContent.split('\n').filter(Boolean);
        for (const l of lines) {
          rightChildren.push(
            new Paragraph({
              bullet: { level: 0 },
              spacing: { after: 20 },
              children: [new TextRun({ text: l.replace(/^[•-]\s*/, '').trim(), size: 18, font: "Arial" })]
            })
          );
        }
      }
    }
  }

  const layoutTable = new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    borders: {
      top: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
      bottom: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
      left: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
      right: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
      insideHorizontal: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
      insideVertical: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
    },
    rows: [
      new TableRow({
        children: [
          new TableCell({
            width: { size: 68, type: WidthType.PERCENTAGE },
            children: leftChildren
          }),
          new TableCell({
            width: { size: 32, type: WidthType.PERCENTAGE },
            children: rightChildren
          })
        ]
      })
    ]
  });

  const doc = new Document({
    sections: [
      {
        properties: {},
        children: [layoutTable]
      }
    ]
  });

  return await Packer.toBuffer(doc);
}

